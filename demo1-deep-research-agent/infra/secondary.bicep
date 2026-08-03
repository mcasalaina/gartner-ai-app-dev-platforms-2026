@description('Base name used for globally unique resource names.')
@minLength(3)
param baseName string

@description('Object ID that receives passwordless data-plane access.')
param principalId string

@description('Name of the primary Foundry account created by azd.')
param foundryAccountName string

@description('Location for FLUX-1.1-pro.')
param imageLocation string = 'westus'

@description('Location for Speech and artifact storage.')
param primaryLocation string = 'westus'

var suffix = uniqueString(subscription().id, resourceGroup().id)
var imageAccountName = take(toLower('${baseName}img${suffix}'), 64)
var speechAccountName = take(toLower('${baseName}speech${suffix}'), 64)
var storageName = 'dra${take(replace(toLower('${baseName}art${suffix}'), '-', ''), 21)}'
var logAnalyticsName = take(toLower('${baseName}-logs-${suffix}'), 63)
var applicationInsightsName = take(toLower('${baseName}-insights-${suffix}'), 260)
var cognitiveServicesUserRole = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  'a97b65f3-24c7-4388-baec-2e87135dc908'
)

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource modelRouter 'Microsoft.CognitiveServices/accounts/deployments@2025-10-01-preview' = {
  parent: foundryAccount
  name: 'model-router'
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'model-router'
      version: '2025-11-18'
    }
    routing: {
      mode: 'balanced'
      models: [
        {
          format: 'OpenAI'
          name: 'gpt-5.4'
          version: '2026-03-05'
        }
        {
          format: 'OpenAI'
          name: 'gpt-5.4-mini'
          version: '2026-03-17'
        }
        {
          format: 'OpenAI'
          name: 'gpt-5.4-nano'
          version: '2026-03-17'
        }
      ]
    }
  }
}

resource imageAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: imageAccountName
  location: imageLocation
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: imageAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource imageDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: imageAccount
  name: 'flux-1-1-pro'
  sku: {
    name: 'GlobalStandard'
    capacity: 1
  }
  properties: {
    model: {
      format: 'Black Forest Labs'
      name: 'FLUX-1.1-pro'
      version: '1'
    }
  }
}

resource imageUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(imageAccount.id, principalId, cognitiveServicesUserRole)
  scope: imageAccount
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: cognitiveServicesUserRole
  }
}

resource speechAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: speechAccountName
  location: primaryLocation
  kind: 'SpeechServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: speechAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource speechUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(speechAccount.id, principalId, cognitiveServicesUserRole)
  scope: speechAccount
  properties: {
    principalId: principalId
    principalType: 'User'
    roleDefinitionId: cognitiveServicesUserRole
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' = {
  name: storageName
  location: primaryLocation
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-06-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource artifacts 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-06-01' = {
  parent: blobService
  name: 'research-artifacts'
  properties: {
    publicAccess: 'None'
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: primaryLocation
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: applicationInsightsName
  location: primaryLocation
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

output imageModelEndpoint string = 'https://${imageAccount.name}.services.ai.azure.com'
output imageModelDeployment string = imageDeployment.name
output speechRegion string = speechAccount.location
output speechEndpoint string = speechAccount.properties.endpoint
output speechResourceId string = speechAccount.id
output storageAccountName string = storage.name
output applicationInsightsConnectionString string = applicationInsights.properties.ConnectionString
