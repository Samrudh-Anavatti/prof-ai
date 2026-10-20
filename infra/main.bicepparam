using 'main.bicep'

param tutorPrincipalIds = [
  'a3ae1104-17d5-48e8-bcf3-2f6a44540dbf' // sam
  '07fc8cc5-7084-41be-99f2-4fb4c2eee135' // punjy (guest in Sam's tenant)
]
param externalTenantId = 'c01293ab-8f78-46af-aa73-1c8fd5a88555' // profai.onmicrosoft.com
param authClientId = 'e79af39b-5c6d-4f3d-90bd-895875d8af11' // "Prof AI web" app registration
param budgetContactEmails = split(readEnvironmentVariable('BUDGET_CONTACT_EMAILS'), ',')
