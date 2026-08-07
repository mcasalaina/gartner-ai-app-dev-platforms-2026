@description('Existing Azure Container Registry name.')
param registryName string

@description('Managed identity principal ID.')
param principalId string

@description('Stable identity resource ID used to generate the assignment name.')
param assignmentSeed string

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource registryRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, assignmentSeed, 'AcrPull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}
