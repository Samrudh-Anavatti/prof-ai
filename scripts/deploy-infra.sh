#!/usr/bin/env bash
# Usage: bash scripts/deploy-infra.sh [--what-if]
set -euo pipefail
cd "$(dirname "$0")/.."

command -v az >/dev/null || az() { az.cmd "$@"; }

[ -f .env ] && set -a && . ./.env && set +a
: "${BUDGET_CONTACT_EMAILS:?Set BUDGET_CONTACT_EMAILS in .env (comma-separated)}"
export BUDGET_CONTACT_EMAILS

resource_group=rg-prof-ai
location=uksouth

az group create -n "$resource_group" -l "$location" --tags project=prof-ai owner=sam -o none

mode=create
[ "${1:-}" = "--what-if" ] && mode=what-if

az deployment group "$mode" \
  -g "$resource_group" \
  -n "prof-ai-$(date +%Y%m%d%H%M%S)" \
  -f infra/main.bicep \
  -p infra/main.bicepparam
