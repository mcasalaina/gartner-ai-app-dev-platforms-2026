@description('Existing Foundry account name.')
param foundryAccountName string = '4iq-foundry-project-resource'

@description('Optimizer deployment name.')
param deploymentName string = 'DeepSeek-V4-Pro-optimizer'

@description('Capacity validated immediately before deployment.')
@minValue(1)
param capacity int = 1

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

resource optimizerDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundryAccount
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: capacity
  }
  properties: {
    model: {
      format: 'DeepSeek'
      name: 'DeepSeek-V4-Pro'
      version: '2026-04-23'
    }
    raiPolicyName: 'Microsoft.Default'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

output optimizerDeploymentName string = optimizerDeployment.name
