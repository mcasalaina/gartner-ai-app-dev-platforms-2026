@description('Azure region. Keep aligned with the selected Foundry project.')
param location string = 'eastus2'

@description('Stable environment label used for tags and names.')
@minLength(2)
@maxLength(20)
param environmentName string = 'gartner-bank'

@description('Existing Log Analytics workspace name.')
param logAnalyticsWorkspaceName string = '4iq-foundry-project-resource-logs'

@description('Existing Application Insights component name.')
param applicationInsightsName string = '4iq-foundry-project-resource-appinsights'

@description('Resource ID of the existing Azure Container Registry.')
param containerRegistryResourceId string

@description('Registry host, for example contoso.azurecr.io.')
param containerRegistryServer string

@description('Fully qualified frontend container image.')
param frontendImage string

@description('Fully qualified authenticated backend container image.')
param backendImage string

@description('Fully qualified Agent 365 bridge container image.')
param bridgeImage string

@description('Fully qualified Entra Auth SDK sidecar image for the Agent 365 bridge.')
param bridgeSidecarImage string

@description('Microsoft Entra tenant ID.')
param entraTenantId string = subscription().tenantId

@description('Web API app registration client ID.')
param webApiClientId string

@description('Web API audience expected in inbound access tokens.')
param webApiAudience string

@description('Web API delegated permission required in inbound tokens.')
param webApiRequiredScope string

@description('Confidential-client secret used only for OBO and stored in Key Vault.')
@secure()
param webApiClientSecret string

@description('Agent 365 Agent User token audience.')
param agentUserAudience string

@description('Existing Agent 365 agent-user object ID.')
param agentUserId string

@description('Existing Agent 365 agent identity client ID.')
param agentIdentityId string

@description('Existing Agent 365 parent blueprint client ID.')
param parentBlueprintId string

@description('Parent blueprint confidential-client secret stored in Key Vault.')
@secure()
param parentBlueprintClientSecret string

@description('Purview sensitivity label ID applied to Agent 365 email replies.')
param agentEmailGeneralLabelId string = 'defa4170-0d19-0005-0004-bc88714345d2'

@description('Purview sensitivity label name applied to Agent 365 email replies.')
param agentEmailGeneralLabelName string = 'All Employees (unrestricted)'

@description('Comma-separated Cc recipients the Agent 365 email handler may honor.')
param agentEmailReplyCcAllowlist string = 'mcasalaina.local@cam3652609.onmicrosoft.com'

@description('Comma-separated reviewer app roles.')
param reviewerRoles string = 'BankServicing.ContentReviewer'

@description('Comma-separated administrator app roles.')
param adminRoles string = 'BankServicing.Admin'

@description('Existing Foundry project endpoint.')
param foundryProjectEndpoint string = 'https://4iq-foundry-project-resource.services.ai.azure.com/api/projects/4iq-foundry-project'

@description('Voice Live account endpoint.')
param voiceLiveEndpoint string = 'https://4iq-foundry-project-resource.services.ai.azure.com'

@description('Voice Live voice implementation type.')
param voiceLiveVoiceType string = 'azure-standard'

@description('Voice Live multilingual voice name.')
param voiceLiveVoice string = 'en-US-AlloyTurboMultilingualNeural'

@description('Enable synchronized avatar output.')
param voiceLiveAvatarEnabled bool = true

@description('Standard or custom photo avatar character name.')
param voiceLiveAvatarCharacter string = 'amara'

@description('Photo avatar base model.')
param voiceLiveAvatarModel string = 'vasa-1'

@description('Whether the configured photo avatar is custom.')
param voiceLiveAvatarCustomized bool = false

@description('Allowed browser origin after frontend deployment. Empty uses the generated frontend URL.')
param allowedBrowserOrigin string = ''

var token = uniqueString(subscription().id, resourceGroup().id, environmentName)
var tags = {
  workload: 'bank-servicing-agent'
  environment: environmentName
  demos: 'gartner-2-4'
}
var frontendIdentityName = 'id-bank-web-${token}'
var backendIdentityName = 'id-bank-api-${token}'
var bridgeIdentityName = 'id-bank-bridge-${token}'
var storageName = 'stbank${token}'
var keyVaultName = take('kv-bank-svc-${token}', 24)
var environmentResourceName = 'cae-bank-servicing-${token}'
var frontendName = 'bank-servicing-web'
var backendName = 'bank-servicing-api'
var bridgeName = 'bank-servicing-agent-bridge-a365'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource frontendIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: frontendIdentityName
  location: location
  tags: tags
}

resource backendIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: backendIdentityName
  location: location
  tags: tags
}

resource bridgeIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: bridgeIdentityName
  location: location
  tags: tags
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    changeFeed: {
      enabled: true
      retentionInDays: 30
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }
    isVersioningEnabled: true
  }
}

resource contentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'content'
  properties: {
    publicAccess: 'None'
  }
}

resource mediaContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'media'
  properties: {
    publicAccess: 'None'
  }
}

resource evaluationContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'evaluation'
  properties: {
    publicAccess: 'None'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    tenantId: entraTenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    enableSoftDelete: true
    publicNetworkAccess: 'Enabled'
    softDeleteRetentionInDays: 90
  }
}

resource oboSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'web-api-client-secret'
  properties: {
    value: webApiClientSecret
  }
}

resource blueprintSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'agent365-blueprint-client-secret'
  properties: {
    value: parentBlueprintClientSecret
  }
}

resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, backendIdentity.id, 'Storage Blob Data Contributor')
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    )
    principalId: backendIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backendKeyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, backendIdentity.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'
    )
    principalId: backendIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource bridgeKeyVaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, bridgeIdentity.id, 'Key Vault Secrets User')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4633458b-17de-408a-b874-0445c86b69e6'
    )
    principalId: bridgeIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

module frontendRegistryRole 'acr-pull-role.bicep' = {
  name: 'acr-pull-frontend-${token}'
  scope: resourceGroup(
    split(containerRegistryResourceId, '/')[2],
    split(containerRegistryResourceId, '/')[4]
  )
  params: {
    registryName: last(split(containerRegistryResourceId, '/'))
    principalId: frontendIdentity.properties.principalId
    assignmentSeed: frontendIdentity.id
  }
}

module backendRegistryRole 'acr-pull-role.bicep' = {
  name: 'acr-pull-backend-${token}'
  scope: resourceGroup(
    split(containerRegistryResourceId, '/')[2],
    split(containerRegistryResourceId, '/')[4]
  )
  params: {
    registryName: last(split(containerRegistryResourceId, '/'))
    principalId: backendIdentity.properties.principalId
    assignmentSeed: backendIdentity.id
  }
}

module bridgeRegistryRole 'acr-pull-role.bicep' = {
  name: 'acr-pull-bridge-${token}'
  scope: resourceGroup(
    split(containerRegistryResourceId, '/')[2],
    split(containerRegistryResourceId, '/')[4]
  )
  params: {
    registryName: last(split(containerRegistryResourceId, '/'))
    principalId: bridgeIdentity.properties.principalId
    assignmentSeed: bridgeIdentity.id
  }
}

resource managedEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: environmentResourceName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
    zoneRedundant: false
  }
}

resource frontend 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${frontendIdentity.id}': {}
    }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        allowInsecure: false
        external: true
        targetPort: 8080
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistryServer
          identity: frontendIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: frontendImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
  dependsOn: [
    frontendRegistryRole
  ]
}

var effectiveOrigin = empty(allowedBrowserOrigin)
  ? 'https://${frontend.properties.configuration.ingress.fqdn}'
  : allowedBrowserOrigin

resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: backendName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${backendIdentity.id}': {}
    }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: [
            effectiveOrigin
          ]
          allowedMethods: [
            'GET'
            'POST'
            'OPTIONS'
          ]
          allowedHeaders: [
            'authorization'
            'content-type'
            'traceparent'
            'tracestate'
            'baggage'
            'x-client-demo-mode'
          ]
        }
        external: true
        targetPort: 8080
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistryServer
          identity: backendIdentity.id
        }
      ]
      secrets: [
        {
          name: 'web-api-client-secret'
          keyVaultUrl: oboSecret.properties.secretUri
          identity: backendIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: backendImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APP_ENVIRONMENT'
              value: 'production'
            }
            {
              name: 'ENTRA_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'ENTRA_ALLOWED_ISSUERS'
              value: '${environment().authentication.loginEndpoint}${entraTenantId}/v2.0,https://sts.windows.net/${entraTenantId}/'
            }
            {
              name: 'ENTRA_API_AUDIENCE'
              value: webApiAudience
            }
            {
              name: 'ENTRA_CLIENT_ID'
              value: webApiClientId
            }
            {
              name: 'ENTRA_CLIENT_SECRET'
              secretRef: 'web-api-client-secret'
            }
            {
              name: 'ENTRA_REQUIRED_SCOPE'
              value: webApiRequiredScope
            }
            {
              name: 'REVIEWER_ROLES'
              value: reviewerRoles
            }
            {
              name: 'ADMIN_ROLES'
              value: adminRoles
            }
            {
              name: 'ALLOWED_DEMO_MODES'
              value: 'service_discovery,customer_servicing,avatar_marketing'
            }
            {
              name: 'FOUNDRY_PROJECT_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'FOUNDRY_AGENT_NAME'
              value: 'bank-servicing-agent'
            }
            {
              name: 'FOUNDRY_MODEL_NAME'
              value: 'gpt-5.4-mini'
            }
            {
              name: 'FOUNDRY_REQUEST_TIMEOUT_SECONDS'
              value: '360'
            }
            {
              name: 'VOICE_LIVE_ENDPOINT'
              value: voiceLiveEndpoint
            }
            {
              name: 'VOICE_LIVE_API_VERSION'
              value: '2026-04-10'
            }
            {
              name: 'VOICE_LIVE_PROJECT_NAME'
              value: '4iq-foundry-project'
            }
            {
              name: 'VOICE_LIVE_AGENT_NAME'
              value: 'bank-servicing-agent'
            }
            {
              name: 'VOICE_LIVE_VOICE'
              value: voiceLiveVoice
            }
            {
              name: 'VOICE_LIVE_VOICE_TYPE'
              value: voiceLiveVoiceType
            }
            {
              name: 'VOICE_LIVE_AVATAR_ENABLED'
              value: string(voiceLiveAvatarEnabled)
            }
            {
              name: 'VOICE_LIVE_AVATAR_CHARACTER'
              value: voiceLiveAvatarCharacter
            }
            {
              name: 'VOICE_LIVE_AVATAR_MODEL'
              value: voiceLiveAvatarModel
            }
            {
              name: 'VOICE_LIVE_AVATAR_CUSTOMIZED'
              value: string(voiceLiveAvatarCustomized)
            }
            {
              name: 'CONTENT_STORAGE_ACCOUNT_URL'
              value: storage.properties.primaryEndpoints.blob
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: backendIdentity.properties.clientId
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsights.properties.ConnectionString
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
  dependsOn: [
    backendKeyVaultRole
    backendRegistryRole
  ]
}

resource bridge 'Microsoft.App/containerApps@2024-03-01' = {
  name: bridgeName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${bridgeIdentity.id}': {}
    }
  }
  properties: {
    environmentId: managedEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        allowInsecure: false
        external: true
        targetPort: 8080
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistryServer
          identity: bridgeIdentity.id
        }
      ]
      secrets: [
        {
          name: 'blueprint-client-secret'
          keyVaultUrl: blueprintSecret.properties.secretUri
          identity: bridgeIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'bridge'
          image: bridgeImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'ENTRA_TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'AGENT_USER_AUDIENCE'
              value: agentUserAudience
            }
            {
              name: 'AGENT_USER_ID'
              value: agentUserId
            }
            {
              name: 'AGENT_IDENTITY_ID'
              value: agentIdentityId
            }
            {
              name: 'PARENT_BLUEPRINT_ID'
              value: parentBlueprintId
            }
            {
              name: 'AGENT_EMAIL_GENERAL_LABEL_ID'
              value: agentEmailGeneralLabelId
            }
            {
              name: 'AGENT_EMAIL_GENERAL_LABEL_NAME'
              value: agentEmailGeneralLabelName
            }
            {
              name: 'AGENT_EMAIL_REPLY_CC_ALLOWLIST'
              value: agentEmailReplyCcAllowlist
            }
            {
              name: 'SIDE_CAR_SERVICE_NAME'
              value: 'Foundry'
            }
            {
              name: 'SIDE_CAR_BASE_URL'
              value: 'http://127.0.0.1:8081'
            }
            {
              name: 'FOUNDRY_PROJECT_ENDPOINT'
              value: foundryProjectEndpoint
            }
            {
              name: 'FOUNDRY_AGENT_NAME'
              value: 'bank-servicing-agent'
            }
            {
              name: 'FOUNDRY_REQUEST_TIMEOUT_SECONDS'
              value: '360'
            }
            {
              name: 'FOUNDRY_MODEL_NAME'
              value: 'gpt-5.4-mini'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: applicationInsights.properties.ConnectionString
            }
            {
              name: 'PORT'
              value: '8080'
            }
            {
              name: 'BRIDGE_IDENTITY_SMOKE_ENABLED'
              value: 'true'
            }
            {
              name: 'CLIENT_ID'
              value: parentBlueprintId
            }
            {
              name: 'CLIENT_SECRET'
              secretRef: 'blueprint-client-secret'
            }
            {
              name: 'TENANT_ID'
              value: entraTenantId
            }
            {
              name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTID'
              value: parentBlueprintId
            }
            {
              name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__CLIENTSECRET'
              secretRef: 'blueprint-client-secret'
            }
            {
              name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__TENANTID'
              value: entraTenantId
            }
            {
              name: 'CONNECTIONS__SERVICE_CONNECTION__SETTINGS__SCOPES'
              value: '5a807f24-c9de-44ee-a3a7-329e88a00ffc/.default'
            }
            {
              name: 'CONNECTIONSMAP__0__SERVICEURL'
              value: '*'
            }
            {
              name: 'CONNECTIONSMAP__0__CONNECTION'
              value: 'SERVICE_CONNECTION'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: bridgeIdentity.properties.clientId
            }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 8080
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 12
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8080
              }
              initialDelaySeconds: 20
              periodSeconds: 30
              failureThreshold: 3
            }
          ]
        }
        {
          name: 'entra-auth-sidecar'
          image: bridgeSidecarImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'ASPNETCORE_ENVIRONMENT'
              value: 'Production'
            }
            {
              name: 'ASPNETCORE_URLS'
              value: 'http://127.0.0.1:8081'
            }
            {
              name: 'Sidecar__AllowOverrides__GetAuthorizationHeaderUnauthenticated'
              value: 'true'
            }
            {
              name: 'AzureAd__Instance'
              value: environment().authentication.loginEndpoint
            }
            {
              name: 'AzureAd__TenantId'
              value: entraTenantId
            }
            {
              name: 'AzureAd__ClientId'
              value: parentBlueprintId
            }
            {
              name: 'AzureAd__ClientCredentials__0__SourceType'
              value: 'ClientSecret'
            }
            {
              name: 'AzureAd__ClientCredentials__0__ClientSecret'
              secretRef: 'blueprint-client-secret'
            }
            {
              name: 'DownstreamApis__Foundry__BaseUrl'
              value: foundryProjectEndpoint
            }
            {
              name: 'DownstreamApis__Foundry__Scopes__0'
              value: 'https://ai.azure.com/.default'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
  dependsOn: [
    bridgeKeyVaultRole
    bridgeRegistryRole
  ]
}

output frontendUrl string = 'https://${frontend.properties.configuration.ingress.fqdn}'
output backendUrl string = 'https://${backend.properties.configuration.ingress.fqdn}'
output bridgeUrl string = 'https://${bridge.properties.configuration.ingress.fqdn}'
output storageAccountName string = storage.name
output keyVaultName string = keyVault.name
output frontendIdentityClientId string = frontendIdentity.properties.clientId
output backendIdentityClientId string = backendIdentity.properties.clientId
output bridgeIdentityClientId string = bridgeIdentity.properties.clientId
