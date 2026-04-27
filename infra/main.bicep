// Art of Clawpilot — hosted foundation infrastructure
//
// Provisions:
//   - Azure Static Web App for the frontend deploy path
//   - Azure Key Vault with RBAC for hosted runner secrets/config
//   - Log Analytics + Container Apps managed environment
//   - User-assigned managed identity for the hosted daily runner
//   - Manual-first Azure Container Apps Job shell for the hosted runner
//   - Azure Function App HTTP API shell for internal manual run triggers
//   - Role assignments so the job identity can read Key Vault secrets,
//     call the existing Foundry / Azure AI Services resource, and optionally
//     pull from Azure Container Registry with managed identity
//   - Role assignments so the Function identity can read the API key secret
//     and start the existing Container Apps Job with per-run overrides

targetScope = 'resourceGroup'

@description('Short prefix for resource names. Lowercase, 3-8 chars.')
@minLength(3)
@maxLength(8)
param namePrefix string = 'artclaw'

@description('Azure region for all resources.')
param location string = 'eastus2'

@description('GitHub repository URL for the SWA build integration.')
param repositoryUrl string = 'https://github.com/MaxBush6299/ArtofClawpilot'

@description('Branch the SWA should track.')
param branch string = 'main'

@description('GitHub PAT or deployment token for the SWA. Leave empty if you will configure deployment after creation.')
@secure()
param repositoryToken string = ''

@description('Resource ID of the existing Foundry / Azure AI Services account hosting the hosted models.')
param foundryResourceId string

@description('Azure OpenAI-compatible endpoint URL for the hosted reasoning deployment. Stored in Key Vault and injected into the job.')
param foundryReasoningEndpoint string = 'https://example.openai.azure.com'

@description('Deployment name for the hosted reasoning model. Stored in Key Vault and injected into the job.')
param foundryReasoningDeploymentName string = 'grok-4-20-reasoning'

@description('API version for the hosted reasoning deployment. Injected into the job as runtime config.')
param foundryReasoningApiVersion string = '2024-10-21'

@description('MAI image-generation endpoint URL for the hosted image deployment. Stored in Key Vault and injected into the job.')
param foundryImageEndpoint string = 'https://example.services.ai.azure.com'

@description('Deployment name for the hosted image model. Stored in Key Vault and injected into the job.')
param foundryImageDeploymentName string = 'mai-image-2e'

@description('Container image to execute in the hosted daily runner job.')
param jobImage string = 'ghcr.io/maxbush6299/artofclawpilot-runner:latest'

@description('Trigger mode for the hosted daily runner job. Keep Manual until hosted smoke proof passes.')
@allowed([
  'Manual'
  'Schedule'
])
param jobTriggerType string = 'Manual'

@description('Cron expression for the scheduled daily runner. Azure Container Apps Jobs evaluate the schedule in UTC.')
param jobScheduleCron string = '0 7 * * *'

@description('vCPU allocated to the hosted daily runner container.')
param jobCpu string = '0.5'

@description('Memory allocated to the hosted daily runner container.')
param jobMemory string = '1Gi'

@description('Timeout, in seconds, for each job replica.')
param jobReplicaTimeout int = 1800

@description('Retry attempts for a failed job replica before the execution fails.')
param jobReplicaRetryLimit int = 1

@description('Optional Azure Container Registry login server for managed-identity image pulls.')
param containerRegistryServer string = ''

@description('Optional resource ID of the Azure Container Registry that hosts the job image. When provided, the job identity receives AcrPull.')
param containerRegistryResourceId string = ''

@description('GitHub owner that the hosted runner will clone and push to.')
param githubOwner string = 'MaxBush6299'

@description('GitHub repository name that the hosted runner will clone and push to.')
param githubRepo string = 'ArtofClawpilot'

@description('GitHub branch that the hosted runner writes to.')
param githubBranch string = 'main'

@description('GitHub App ID used by the hosted runner. Stored in Key Vault.')
param githubAppId string = 'replace-me'

@description('GitHub App installation ID used by the hosted runner. Stored in Key Vault.')
param githubAppInstallationId string = 'replace-me'

@description('GitHub App private key PEM used by the hosted runner. Stored in Key Vault.')
@secure()
param githubAppPrivateKey string = ''

@description('Default git author name for hosted commits.')
param gitAuthorName string = 'Art of Clawpilot Bot'

@description('Default git author email for hosted commits.')
param gitAuthorEmail string = 'artofclawpilot-bot@users.noreply.github.com'

@description('Optional command executed inside the fresh clone before any commit/push step.')
param hostedRunnerCommand string = 'python3 -m orchestrator.main --repo-root "$REPO_WORKSPACE" --run-date "$RUN_DATE_UTC" --run-id "$RUN_ID"'

@description('Optional fixed UTC run date injected into the hosted runner. Useful for hosted smoke and idempotency replay.')
param hostedRunDateOverride string = ''

@description('Optional run identifier for manual execution. Scheduled runs use runId=scheduled-{runDate}.')
param hostedRunId string = ''

@description('Trigger source for this execution: scheduled, manual-api, or manual-cli.')
@allowed([
  'scheduled'
  'manual-api'
  'manual-cli'
])
param hostedTriggerSource string = 'scheduled'

@description('Whether the hosted bootstrap should push changes when the runner command mutates the clone.')
param hostedPushChanges bool = false

@description('Linux Functions worker runtime for the internal Clawpilot API. Keep aligned with Kyle API code at deployment time.')
@allowed([
  'node'
  'python'
])
param functionWorkerRuntime string = 'node'

@description('Flex Consumption runtime version for the internal Clawpilot API. Default is Node.js 20 for the planned JavaScript API implementation.')
@allowed([
  '20'
  '3.11'
])
param functionRuntimeVersion string = '20'

@description('Maximum scale-out instance count for the Function App on Flex Consumption.')
@minValue(40)
@maxValue(1000)
param functionMaximumInstanceCount int = 40

@description('Memory size in MB for Function App instances on Flex Consumption.')
@allowed([
  2048
  4096
])
param functionInstanceMemoryMB int = 2048

@description('Key Vault secret name containing the Phase 1 Clawpilot API key.')
param clawpilotApiKeySecretName string = 'clawpilot-api-key'

@description('Optional initial value for the Clawpilot API key secret. Leave empty to avoid writing a secret from deployment; create/rotate it post-deploy with az keyvault secret set.')
@secure()
param clawpilotApiKey string = ''

@description('Built-in role assigned to the Function identity at the Container Apps Job scope. Default is Container Apps Jobs Operator, which can read and start jobs. Use Container Apps Jobs Contributor only if Kyle API code must persistently update the job definition before starting it.')
@allowed([
  'b9a307c4-5aa3-4b52-ba60-2b17c136cd7b'
  '4e3d2b60-56ae-4dc6-a233-09c8e5a82e68'
])
param functionContainerAppsJobRoleDefinitionId string = 'b9a307c4-5aa3-4b52-ba60-2b17c136cd7b'

var suffix = uniqueString(resourceGroup().id, namePrefix)
var swaName = '${namePrefix}-swa-${suffix}'
var kvName = take('${namePrefix}kv${suffix}', 24)
var workspaceName = '${namePrefix}-logs-${suffix}'
var managedEnvironmentName = '${namePrefix}-acae-${suffix}'
var jobIdentityName = '${namePrefix}-job-mi-${suffix}'
var dailyJobName = '${namePrefix}-daily-job-${suffix}'
var functionStorageName = take('${namePrefix}fnst${suffix}', 24)
var functionPlanName = '${namePrefix}-api-plan-${suffix}'
var functionIdentityName = '${namePrefix}-api-mi-${suffix}'
var functionAppName = '${namePrefix}-api-${suffix}'
var functionAppInsightsName = '${namePrefix}-api-ai-${suffix}'
var functionDeploymentContainerName = 'app-package-${take(functionAppName, 32)}-${take(suffix, 7)}'

var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var roleCognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var roleStorageBlobDataOwner = 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
var roleStorageQueueDataContributor = '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
var roleStorageTableDataContributor = '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3'
var roleMonitoringMetricsPublisher = '3913510d-42f4-4e42-8a64-420c390055eb'
var hasGitHubAppConfig = !empty(githubAppPrivateKey) && githubAppId != 'replace-me' && githubAppInstallationId != 'replace-me'

var jobIdentityMap = {
  '${jobIdentity.id}': {}
}

var functionIdentityMap = {
  '${functionIdentity.id}': {}
}

var foundryJobSecretSpecs = [
  {
    identity: jobIdentity.id
    name: 'foundry-reasoning-endpoint'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/foundry-reasoning-endpoint'
  }
  {
    identity: jobIdentity.id
    name: 'foundry-image-endpoint'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/foundry-image-endpoint'
  }
  {
    identity: jobIdentity.id
    name: 'foundry-endpoint'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/foundry-endpoint'
  }
  {
    identity: jobIdentity.id
    name: 'foundry-reasoning-deployment'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/foundry-reasoning-deployment-name'
  }
  {
    identity: jobIdentity.id
    name: 'foundry-reasoning-api-version'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/foundry-reasoning-api-version'
  }
  {
    identity: jobIdentity.id
    name: 'foundry-image-deployment'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/foundry-image-deployment-name'
  }
  {
    identity: jobIdentity.id
    name: 'foundry-deployment'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/foundry-deployment-name'
  }
]

var githubJobSecretSpecs = [
  {
    identity: jobIdentity.id
    name: 'github-app-id'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/github-app-id'
  }
  {
    identity: jobIdentity.id
    name: 'github-app-installation-id'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/github-app-installation-id'
  }
  {
    identity: jobIdentity.id
    name: 'github-app-private-key'
    keyVaultUrl: '${keyVault.properties.vaultUri}secrets/github-app-private-key'
  }
]

var jobSecretSpecs = hasGitHubAppConfig
  ? concat(foundryJobSecretSpecs, githubJobSecretSpecs)
  : foundryJobSecretSpecs

var baseJobEnvVars = concat([
  {
    name: 'HOSTED_JOB_NAME'
    value: dailyJobName
  }
  {
    name: 'AZURE_CLIENT_ID'
    value: jobIdentity.properties.clientId
  }
  {
    name: 'KEY_VAULT_URL'
    value: keyVault.properties.vaultUri
  }
  {
    name: 'FOUNDRY_REASONING_ENDPOINT'
    secretRef: 'foundry-reasoning-endpoint'
  }
  {
    name: 'FOUNDRY_IMAGE_ENDPOINT'
    secretRef: 'foundry-image-endpoint'
  }
  {
    name: 'FOUNDRY_ENDPOINT'
    secretRef: 'foundry-endpoint'
  }
  {
    name: 'FOUNDRY_REASONING_DEPLOYMENT'
    secretRef: 'foundry-reasoning-deployment'
  }
  {
    name: 'FOUNDRY_REASONING_API_VERSION'
    secretRef: 'foundry-reasoning-api-version'
  }
  {
    name: 'FOUNDRY_IMAGE_DEPLOYMENT'
    secretRef: 'foundry-image-deployment'
  }
  {
    name: 'FOUNDRY_DEPLOYMENT'
    secretRef: 'foundry-deployment'
  }
  {
    name: 'GITHUB_OWNER'
    value: githubOwner
  }
  {
    name: 'GITHUB_REPO'
    value: githubRepo
  }
  {
    name: 'GITHUB_BRANCH'
    value: githubBranch
  }
  {
    name: 'GIT_AUTHOR_NAME'
    value: gitAuthorName
  }
  {
    name: 'GIT_AUTHOR_EMAIL'
    value: gitAuthorEmail
  }
  {
    name: 'HOSTED_RUNNER_COMMAND'
    value: hostedRunnerCommand
  }
  {
    name: 'PYTHONUNBUFFERED'
    value: '1'
  }
  {
    name: 'PYTHONDONTWRITEBYTECODE'
    value: '1'
  }
  {
    name: 'HOSTED_PUSH_CHANGES'
    value: hostedPushChanges ? 'true' : 'false'
  }
], hasGitHubAppConfig ? [
  {
    name: 'GITHUB_APP_ID'
    secretRef: 'github-app-id'
  }
  {
    name: 'GITHUB_APP_INSTALLATION_ID'
    secretRef: 'github-app-installation-id'
  }
  {
    name: 'GITHUB_APP_PRIVATE_KEY'
    secretRef: 'github-app-private-key'
  }
] : [])

var jobEnvVars = concat(baseJobEnvVars, !empty(hostedRunDateOverride) ? [{
  name: 'RUN_DATE_UTC'
  value: hostedRunDateOverride
}] : [], [
  {
    name: 'RUN_ID'
    value: !empty(hostedRunId) ? hostedRunId : ''
  }
  {
    name: 'TRIGGER_SOURCE'
    value: hostedTriggerSource
  }
])

var baseJobConfiguration = {
  triggerType: jobTriggerType
  replicaTimeout: jobReplicaTimeout
  replicaRetryLimit: jobReplicaRetryLimit
  secrets: jobSecretSpecs
  registries: empty(containerRegistryServer) ? [] : [
    {
      server: containerRegistryServer
      identity: jobIdentity.id
    }
  ]
}

var jobConfiguration = union(
  baseJobConfiguration,
  jobTriggerType == 'Schedule'
    ? {
        scheduleTriggerConfig: {
          cronExpression: jobScheduleCron
          parallelism: 1
          replicaCompletionCount: 1
        }
      }
    : {}
)

// -------------------- Static Web App --------------------
resource swa 'Microsoft.Web/staticSites@2024-04-01' = {
  name: swaName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    repositoryUrl: repositoryUrl
    branch: branch
    repositoryToken: empty(repositoryToken) ? null : repositoryToken
    buildProperties: {
      appLocation: '/'
      outputLocation: 'dist'
      appBuildCommand: 'npm run build'
    }
  }
}

// -------------------- Key Vault --------------------
resource keyVault 'Microsoft.KeyVault/vaults@2024-04-01-preview' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
  }
}

resource secretFoundryReasoningEndpoint 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-reasoning-endpoint'
  properties: {
    value: foundryReasoningEndpoint
  }
}

resource secretFoundryImageEndpoint 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-image-endpoint'
  properties: {
    value: foundryImageEndpoint
  }
}

resource secretFoundryEndpoint 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-endpoint'
  properties: {
    value: foundryImageEndpoint
  }
}

resource secretFoundryReasoningDeployment 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-reasoning-deployment-name'
  properties: {
    value: foundryReasoningDeploymentName
  }
}

resource secretFoundryReasoningApiVersion 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-reasoning-api-version'
  properties: {
    value: foundryReasoningApiVersion
  }
}

resource secretFoundryImageDeployment 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-image-deployment-name'
  properties: {
    value: foundryImageDeploymentName
  }
}

resource secretFoundryDeploymentAlias 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-deployment-name'
  properties: {
    value: foundryImageDeploymentName
  }
}

resource secretGitHubAppId 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = if (hasGitHubAppConfig) {
  parent: keyVault
  name: 'github-app-id'
  properties: {
    value: githubAppId
  }
}

resource secretGitHubAppInstallationId 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = if (hasGitHubAppConfig) {
  parent: keyVault
  name: 'github-app-installation-id'
  properties: {
    value: githubAppInstallationId
  }
}

resource secretGitHubAppPrivateKey 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = if (hasGitHubAppConfig) {
  parent: keyVault
  name: 'github-app-private-key'
  properties: {
    value: githubAppPrivateKey
  }
}

resource secretClawpilotApiKey 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = if (!empty(clawpilotApiKey)) {
  parent: keyVault
  name: clawpilotApiKeySecretName
  properties: {
    value: clawpilotApiKey
  }
}

// -------------------- Hosted runner identity --------------------
resource jobIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: jobIdentityName
  location: location
}

resource jobKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, jobIdentity.id, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    principalId: jobIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsUser)
  }
}

module foundryRoleModule 'modules/foundryRole.bicep' = {
  name: 'foundryRoleAssignment'
  scope: resourceGroup(split(foundryResourceId, '/')[2], split(foundryResourceId, '/')[4])
  params: {
    foundryResourceName: last(split(foundryResourceId, '/'))
    principalId: jobIdentity.properties.principalId
    roleDefinitionId: roleCognitiveServicesUser
  }
}

module containerRegistryRoleModule 'modules/containerRegistryRole.bicep' = if (!empty(containerRegistryResourceId)) {
  name: 'containerRegistryRoleAssignment'
  scope: resourceGroup(split(containerRegistryResourceId, '/')[2], split(containerRegistryResourceId, '/')[4])
  params: {
    registryName: last(split(containerRegistryResourceId, '/'))
    principalId: jobIdentity.properties.principalId
    roleDefinitionId: roleAcrPull
  }
}

// -------------------- Observability + Container Apps --------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  properties: {
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: managedEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

resource hostedDailyRunnerJob 'Microsoft.App/jobs@2024-03-01' = {
  name: dailyJobName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: jobIdentityMap
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: jobConfiguration
    template: {
      containers: [
        {
          name: 'runner'
          image: jobImage
          command: [
            'node'
            'scripts/hosted-bootstrap.mjs'
          ]
          env: jobEnvVars
          resources: {
            cpu: json(jobCpu)
            memory: jobMemory
          }
        }
      ]
    }
  }
}

// -------------------- Internal manual-run API --------------------
resource functionIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: functionIdentityName
  location: location
}

resource functionStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: functionStorageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }

  resource blobService 'blobServices' = {
    name: 'default'

    resource deploymentContainer 'containers' = {
      name: functionDeploymentContainerName
      properties: {
        publicAccess: 'None'
      }
    }
  }
}

resource functionPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: functionPlanName
  location: location
  kind: 'functionapp'
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
  }
  properties: {
    reserved: true
  }
}

resource functionAppInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: functionAppInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    DisableLocalAuth: true
    WorkspaceResourceId: logAnalytics.id
  }
}

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: functionIdentityMap
  }
  properties: {
    serverFarmId: functionPlan.id
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: {
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${functionStorage.properties.primaryEndpoints.blob}${functionDeploymentContainerName}'
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: functionIdentity.id
          }
        }
      }
      scaleAndConcurrency: {
        maximumInstanceCount: functionMaximumInstanceCount
        instanceMemoryMB: functionInstanceMemoryMB
      }
      runtime: {
        name: functionWorkerRuntime
        version: functionRuntimeVersion
      }
    }
  }
  dependsOn: [
    functionStorageBlobOwner
    functionStorageQueueContributor
    functionStorageTableContributor
    functionAppInsightsMetricsPublisher
  ]
}

resource functionAppSettings 'Microsoft.Web/sites/config@2024-04-01' = {
  parent: functionApp
  name: 'appsettings'
  properties: {
    AzureWebJobsStorage__accountName: functionStorage.name
    AzureWebJobsStorage__credential: 'managedidentity'
    AzureWebJobsStorage__clientId: functionIdentity.properties.clientId
    AzureWebJobsStorage__blobServiceUri: functionStorage.properties.primaryEndpoints.blob
    AzureWebJobsStorage__queueServiceUri: functionStorage.properties.primaryEndpoints.queue
    AzureWebJobsStorage__tableServiceUri: functionStorage.properties.primaryEndpoints.table
    APPLICATIONINSIGHTS_CONNECTION_STRING: functionAppInsights.properties.ConnectionString
    APPINSIGHTS_INSTRUMENTATIONKEY: functionAppInsights.properties.InstrumentationKey
    APPLICATIONINSIGHTS_AUTHENTICATION_STRING: 'ClientId=${functionIdentity.properties.clientId};Authorization=AAD'
    AZURE_CLIENT_ID: functionIdentity.properties.clientId
    AZURE_SUBSCRIPTION_ID: subscription().subscriptionId
    AZURE_TENANT_ID: subscription().tenantId
    KEY_VAULT_URL: keyVault.properties.vaultUri
    CLAWPILOT_API_KEY_SECRET_NAME: clawpilotApiKeySecretName
    AZURE_RESOURCE_GROUP: resourceGroup().name
    RESOURCE_GROUP_NAME: resourceGroup().name
    CONTAINER_APP_JOB_RESOURCE_GROUP: resourceGroup().name
    CONTAINER_APP_JOB_NAME: hostedDailyRunnerJob.name
    CONTAINER_APP_JOB_CONTAINER_NAME: 'runner'
    CONTAINER_APP_JOB_RESOURCE_ID: hostedDailyRunnerJob.id
    CONTAINER_APP_ENVIRONMENT_NAME: managedEnvironment.name
    CONTAINER_APP_ENVIRONMENT_ID: managedEnvironment.id
    GITHUB_OWNER: githubOwner
    GITHUB_REPO: githubRepo
    GITHUB_BRANCH: githubBranch
    DEFAULT_TRIGGER_SOURCE: 'manual-api'
  }
}

resource functionStorageBlobOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionStorage.id, functionIdentity.id, roleStorageBlobDataOwner)
  scope: functionStorage
  properties: {
    principalId: functionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageBlobDataOwner)
  }
}

resource functionStorageQueueContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionStorage.id, functionIdentity.id, roleStorageQueueDataContributor)
  scope: functionStorage
  properties: {
    principalId: functionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageQueueDataContributor)
  }
}

resource functionStorageTableContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionStorage.id, functionIdentity.id, roleStorageTableDataContributor)
  scope: functionStorage
  properties: {
    principalId: functionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleStorageTableDataContributor)
  }
}

resource functionAppInsightsMetricsPublisher 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(functionAppInsights.id, functionIdentity.id, roleMonitoringMetricsPublisher)
  scope: functionAppInsights
  properties: {
    principalId: functionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleMonitoringMetricsPublisher)
  }
}

resource functionKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, functionIdentity.id, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    principalId: functionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsUser)
  }
}

resource functionJobOperator 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(hostedDailyRunnerJob.id, functionIdentity.id, functionContainerAppsJobRoleDefinitionId)
  scope: hostedDailyRunnerJob
  properties: {
    principalId: functionIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', functionContainerAppsJobRoleDefinitionId)
  }
}

// -------------------- Outputs --------------------
output swaHostname string = swa.properties.defaultHostname
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output logAnalyticsWorkspaceName string = logAnalytics.name
output logAnalyticsWorkspaceCustomerId string = logAnalytics.properties.customerId
output containerAppsEnvironmentId string = managedEnvironment.id
output hostedJobName string = hostedDailyRunnerJob.name
output hostedJobTriggerType string = jobTriggerType
output jobIdentityPrincipalId string = jobIdentity.properties.principalId
output jobIdentityClientId string = jobIdentity.properties.clientId
output hostedRunDateOverrideApplied string = hostedRunDateOverride
output githubAppConfigApplied bool = hasGitHubAppConfig
output functionAppName string = functionApp.name
output functionAppDefaultHostname string = functionApp.properties.defaultHostName
output functionIdentityPrincipalId string = functionIdentity.properties.principalId
output functionIdentityClientId string = functionIdentity.properties.clientId
output functionAppInsightsName string = functionAppInsights.name
output clawpilotApiKeySecretName string = clawpilotApiKeySecretName
output functionContainerAppsJobRoleDefinitionId string = functionContainerAppsJobRoleDefinitionId
