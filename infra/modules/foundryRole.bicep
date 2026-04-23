// Assigns a built-in role to a principal at the scope of an existing
// Cognitive Services / Foundry account.

@description('Name of the existing Foundry / Azure AI Services account.')
param foundryResourceName string

@description('Object ID of the principal (managed identity) to grant access to.')
param principalId string

@description('Built-in role definition GUID.')
param roleDefinitionId string

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryResourceName
}

resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundry.id, principalId, roleDefinitionId)
  scope: foundry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
  }
}
