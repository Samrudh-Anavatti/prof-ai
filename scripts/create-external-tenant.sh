#!/usr/bin/env bash
# One-off: creates the Entra External ID tenant that holds tutor and student accounts.
set -euo pipefail
command -v az >/dev/null || az() { az.cmd "$@"; }

subscription=$(az account show --query id -o tsv | tr -d '\r')
url="https://management.azure.com/subscriptions/$subscription/resourceGroups/rg-prof-ai/providers/Microsoft.AzureActiveDirectory/ciamDirectories/profai?api-version=2023-05-17-preview"

body=$(mktemp --suffix=.json)
trap 'rm -f "$body"' EXIT
cat > "$body" <<'JSON'
{
  "location": "Europe",
  "sku": {"name": "Standard", "tier": "A0"},
  "tags": {"project": "prof-ai", "owner": "sam"},
  "properties": {"createTenantProperties": {"displayName": "Prof AI", "countryCode": "GB"}}
}
JSON
az rest --method put --url "$url" --headers Content-Type=application/json --body "@$(cygpath -m "$body" 2>/dev/null || echo "$body")" -o none

until state=$(az rest --method get --url "$url" --query properties.provisioningState -o tsv | tr -d '\r') \
  && [ "$state" = "Succeeded" ]; do
  echo "Provisioning: $state"
  [ "$state" = "Failed" ] && exit 1
  sleep 30
done
az rest --method get --url "$url" --query "{tenantId:properties.tenantId,domain:properties.domainName}" -o json
