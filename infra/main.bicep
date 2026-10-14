targetScope = 'resourceGroup'

param location string = resourceGroup().location
param appName string = 'prof-ai'
param owner string = 'sam'
@description('GitHub OIDC subject repo segment: <owner>@<owner id>/<repo>@<repo id>.')
param githubRepo string = 'Samrudh-Anavatti@95168210/prof-ai@1408891815'
param chatModel object = {
  name: 'gpt-5.6-luna'
  version: '2026-07-09'
  capacity: 10
}
@description('Entra object IDs of tutors who upload content and run the app locally.')
param tutorPrincipalIds array
param budgetAmount int = 50
param budgetStartDate string = '2026-10-01'
param budgetContactEmails array

var tags = {
  project: appName
  owner: owner
}
var suffix = take(uniqueString(resourceGroup().id), 6)
var contentContainers = ['sources', 'content', 'answer-keys']
var roles = {
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  blobReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
  blobContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  websiteContributor: 'de139f84-1756-47ae-9be6-808fbbe84772'
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${appName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json('0.5') }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${appName}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${replace(appName, '-', '')}${suffix}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 14 }
    containerDeleteRetentionPolicy: { enabled: true, days: 14 }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for name in contentContainers: {
    parent: blobService
    name: name
    properties: { publicAccess: 'None' }
  }
]

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: 'foundry-${appName}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: 'foundry-${appName}'
    allowProjectManagement: true
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: appName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: chatModel.name
  sku: {
    name: 'GlobalStandard'
    capacity: chatModel.capacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModel.name
      version: chatModel.version
    }
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  dependsOn: [foundryProject]
}

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: 'plan-${appName}'
  location: location
  tags: tags
  kind: 'linux'
  sku: { name: 'B1' }
  properties: { reserved: true }
}

resource webApp 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  tags: tags
  kind: 'app,linux'
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appCommandLine: 'bash startup.sh'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      healthCheckPath: '/healthz'
      appSettings: [
        { name: 'APP_ENV', value: 'production' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'FOUNDRY_ENDPOINT', value: foundry.properties.endpoint }
        { name: 'CHAT_DEPLOYMENT', value: chatDeployment.name }
        { name: 'STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
      ]
    }
  }
}

resource scmBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: webApp
  name: 'scm'
  properties: { allow: false }
}

resource ftpBasicAuth 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: webApp
  name: 'ftp'
  properties: { allow: false }
}

resource deployIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${appName}-deploy'
  location: location
  tags: tags
}

resource githubFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: deployIdentity
  name: 'github-master'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubRepo}:ref:refs/heads/master'
    audiences: ['api://AzureADTokenExchange']
  }
}

resource contentContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' existing = {
  parent: blobService
  name: 'content'
}

resource appReadsContent 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: contentContainer
  name: guid(contentContainer.id, webApp.id, roles.blobReader)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobReader)
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [containers]
}

resource appUsesFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, webApp.id, roles.openAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
    principalId: webApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource deployerDeploysApp 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: webApp
  name: guid(webApp.id, deployIdentity.id, roles.websiteContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.websiteContributor)
    principalId: deployIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource tutorsManageContent 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for id in tutorPrincipalIds: {
    scope: storage
    name: guid(storage.id, id, roles.blobContributor)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobContributor)
      principalId: id
      principalType: 'User'
    }
  }
]

resource tutorsUseFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for id in tutorPrincipalIds: {
    scope: foundry
    name: guid(foundry.id, id, roles.openAiUser)
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
      principalId: id
      principalType: 'User'
    }
  }
]

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: '${appName}-monthly'
  properties: {
    category: 'Cost'
    amount: budgetAmount
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStartDate }
    notifications: {
      actual50: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        contactEmails: budgetContactEmails
      }
      actual90: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 90
        contactEmails: budgetContactEmails
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        thresholdType: 'Forecasted'
        contactEmails: budgetContactEmails
      }
    }
  }
}

output webAppName string = webApp.name
output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output storageAccountName string = storage.name
output foundryEndpoint string = foundry.properties.endpoint
output deployClientId string = deployIdentity.properties.clientId
