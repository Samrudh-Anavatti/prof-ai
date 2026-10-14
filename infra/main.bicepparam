using 'main.bicep'

param tutorPrincipalIds = [
  'a3ae1104-17d5-48e8-bcf3-2f6a44540dbf' // sam
]
param budgetContactEmails = split(readEnvironmentVariable('BUDGET_CONTACT_EMAILS'), ',')
