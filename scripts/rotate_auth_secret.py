"""Rotates the client secret App Service Authentication uses for the External ID app registration.

The new secret goes straight into Key Vault and is never printed. Older secrets are then removed
and the web app restarted so its Key Vault reference picks up the new value.
Run after `az login`:
    .venv/Scripts/python scripts/rotate_auth_secret.py
"""

from datetime import UTC, datetime, timedelta

import requests
from azure.identity import AzureCliCredential

from prof_ai.graph import GraphClient

EXTERNAL_TENANT_ID = "c01293ab-8f78-46af-aa73-1c8fd5a88555"
AUTH_CLIENT_ID = "e79af39b-5c6d-4f3d-90bd-895875d8af11"
SUBSCRIPTION_ID = "7dc9c954-db74-400c-8314-862146e62259"
RESOURCE_GROUP = "rg-prof-ai"
WEB_APP = "prof-ai"
KEY_VAULT = "kv-prof-ai-cjzzqh"
KEY_VAULT_ITEM = "auth-client-secret"
SECRET_LIFETIME = timedelta(days=180)
CREDENTIAL_PREFIX = "app-service-easy-auth"


def main() -> None:
    graph = GraphClient(AzureCliCredential(tenant_id=EXTERNAL_TENANT_ID))
    workforce = AzureCliCredential()
    app = graph.get(f"/applications?$filter=appId eq '{AUTH_CLIENT_ID}'")["value"][0]

    expires = datetime.now(UTC) + SECRET_LIFETIME
    created = graph.post(
        f"/applications/{app['id']}/addPassword",
        {
            "passwordCredential": {
                "displayName": f"{CREDENTIAL_PREFIX} {datetime.now(UTC):%Y-%m-%d}",
                "endDateTime": expires.isoformat(),
            }
        },
    )

    vault_token = workforce.get_token("https://vault.azure.net/.default").token
    requests.put(
        f"https://{KEY_VAULT}.vault.azure.net/secrets/{KEY_VAULT_ITEM}?api-version=7.4",
        json={"value": created["secretText"], "attributes": {"exp": int(expires.timestamp())}},
        headers={"Authorization": f"Bearer {vault_token}"},
        timeout=30,
    ).raise_for_status()

    for credential in app["passwordCredentials"]:
        if credential["displayName"].startswith(CREDENTIAL_PREFIX):
            graph.post(f"/applications/{app['id']}/removePassword", {"keyId": credential["keyId"]})

    arm_token = workforce.get_token("https://management.azure.com/.default").token
    requests.post(
        f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/"
        f"{RESOURCE_GROUP}/providers/Microsoft.Web/sites/{WEB_APP}/restart?api-version=2024-04-01",
        headers={"Authorization": f"Bearer {arm_token}"},
        timeout=60,
    ).raise_for_status()
    print(f"Rotated {KEY_VAULT_ITEM}; expires {expires:%Y-%m-%d}. Web app restarted.")


if __name__ == "__main__":
    main()
