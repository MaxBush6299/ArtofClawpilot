// Art of Clawpilot — infrastructure
//
// Provisions:
//   - Azure Static Web App (system-assigned managed identity)
//   - Azure Key Vault (RBAC, soft-delete enabled) with placeholder secrets
//   - Role assignments so the SWA's managed identity can:
//       * read secrets from Key Vault (Key Vault Secrets User)
//       * call the existing Foundry / AI Services resource (Cognitive Services User)
//
// Foundry / MAI-Image-2e is assumed to already exist; pass its resource ID in.

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

@description('Resource ID of the existing Foundry / Azure AI Services account hosting MAI-Image-2e.')
param foundryResourceId string

@description('Foundry project endpoint URL. Stored as a secret in Key Vault.')
param foundryEndpoint string = 'https://eval-t1.services.ai.azure.com/api/projects/eval-t1-project'

@description('Deployment name for MAI-Image-2e. Stored as a secret in Key Vault.')
param foundryDeploymentName string = 'mai-image-2e'

var suffix = uniqueString(resourceGroup().id, namePrefix)
var swaName = '${namePrefix}-swa-${suffix}'
var kvName = take('${namePrefix}kv${suffix}', 24)

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
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
  }
}

resource secretFoundryEndpoint 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-endpoint'
  properties: {
    value: foundryEndpoint
  }
}

resource secretFoundryDeployment 'Microsoft.KeyVault/vaults/secrets@2024-04-01-preview' = {
  parent: keyVault
  name: 'foundry-deployment-name'
  properties: {
    value: foundryDeploymentName
  }
}

// -------------------- Role assignments --------------------
// Built-in role IDs (constants):
var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var roleCognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908'

resource raKvSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, swa.id, roleKeyVaultSecretsUser)
  scope: keyVault
  properties: {
    principalId: swa.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsUser)
  }
}

// The Foundry resource lives outside this template; assign the role at its scope.
// To make the role assignment scoped to the Foundry resource, deploy this module
// (or a separate one) targeted at that resource group with `existing` references,
// or use a deployment script. For simplicity, we emit it here scoped to the RG
// of the Foundry resource via a nested deployment.

module foundryRoleModule 'modules/foundryRole.bicep' = {
  name: 'foundryRoleAssignment'
  scope: resourceGroup(split(foundryResourceId, '/')[2], split(foundryResourceId, '/')[4])
  params: {
    foundryResourceName: last(split(foundryResourceId, '/'))
    principalId: swa.identity.principalId
    roleDefinitionId: roleCognitiveServicesUser
  }
}

// -------------------- Outputs --------------------
output swaHostname string = swa.properties.defaultHostname
output swaPrincipalId string = swa.identity.principalId
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
