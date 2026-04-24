// Assigns a built-in role to a principal at the scope of an existing
// Azure Container Registry resource.

@description('Name of the existing Azure Container Registry.')
param registryName string

@description('Object ID of the principal (managed identity) to grant access to.')
param principalId string

@description('Built-in role definition GUID.')
param roleDefinitionId string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, principalId, roleDefinitionId)
  scope: registry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
  }
}
