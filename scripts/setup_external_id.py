"""Configures the External ID tenant: web app registration, consent, email-OTP user flow.

Idempotent. Before the first run, enable "Email OTP" in the External ID tenant's authentication
methods (Entra admin center); the Azure CLI's Graph token can't change that policy.
Run as a tenant admin after `az login`:
    .venv/Scripts/python scripts/setup_external_id.py
Then run scripts/rotate_auth_secret.py to give App Service its client secret.
"""

import json

from azure.identity import AzureCliCredential

from prof_ai.graph import GraphClient, GraphError

EXTERNAL_TENANT_ID = "c01293ab-8f78-46af-aa73-1c8fd5a88555"
APP_NAME = "Prof AI web"
USER_FLOW_NAME = "prof-ai-email-otp"
REDIRECT_URIS = [
    "https://prof-ai.azurewebsites.net/.auth/login/aad/callback",
]
ODATA = "#microsoft.graph."
SIGN_UP_FLOW_TYPE = "ExternalUsersSelfServiceSignUp"
MICROSOFT_GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"
SIGN_IN_SCOPES = "openid profile email offline_access"


def find_one(graph: GraphClient, path: str) -> dict | None:
    items = graph.get(path)["value"]
    return items[0] if items else None


def ensure_app(graph: GraphClient) -> dict:
    app = find_one(graph, f"/applications?$filter=displayName eq '{APP_NAME}'")
    # App Service Authentication signs in with the hybrid flow (response_type=code id_token).
    web = {"redirectUris": REDIRECT_URIS, "implicitGrantSettings": {"enableIdTokenIssuance": True}}
    if app:
        graph.patch(f"/applications/{app['id']}", {"web": web})
        return app
    return graph.post(
        "/applications",
        {"displayName": APP_NAME, "signInAudience": "AzureADMyOrg", "web": web},
    )


def ensure_service_principal(graph: GraphClient, app_id: str) -> dict:
    sp = find_one(graph, f"/servicePrincipals?$filter=appId eq '{app_id}'")
    return sp or graph.post("/servicePrincipals", {"appId": app_id})


def ensure_sign_in_consent(graph: GraphClient, client_sp_id: str) -> None:
    graph_sp = find_one(graph, f"/servicePrincipals?$filter=appId eq '{MICROSOFT_GRAPH_APP_ID}'")
    existing = find_one(
        graph,
        f"/oauth2PermissionGrants?$filter=clientId eq '{client_sp_id}' "
        f"and resourceId eq '{graph_sp['id']}'",
    )
    if existing:
        graph.patch(f"/oauth2PermissionGrants/{existing['id']}", {"scope": SIGN_IN_SCOPES})
        return
    graph.post(
        "/oauth2PermissionGrants",
        {
            "clientId": client_sp_id,
            "consentType": "AllPrincipals",
            "resourceId": graph_sp["id"],
            "scope": SIGN_IN_SCOPES,
        },
    )


def ensure_user_flow(graph: GraphClient, app_id: str) -> dict:
    flows = graph.get("/identity/authenticationEventsFlows")["value"]
    flow = next((f for f in flows if f["displayName"] == USER_FLOW_NAME), None)
    if not flow:
        flow = graph.post(
            "/identity/authenticationEventsFlows",
            {
                "@odata.type": "#microsoft.graph.externalUsersSelfServiceSignUpEventsFlow",
                "displayName": USER_FLOW_NAME,
                "onInteractiveAuthFlowStart": {
                    "@odata.type": ODATA + "onInteractiveAuthFlowStart" + SIGN_UP_FLOW_TYPE,
                    "isSignUpAllowed": False,
                },
                "onAuthenticationMethodLoadStart": {
                    "@odata.type": ODATA + "onAuthenticationMethodLoadStart" + SIGN_UP_FLOW_TYPE,
                    "identityProviders": [{"id": "EmailOtpSignup-OAUTH"}],
                },
            },
        )
    linked = graph.get(
        f"/identity/authenticationEventsFlows/{flow['id']}/conditions/applications/includeApplications"
    )["value"]
    if not any(app["appId"] == app_id for app in linked):
        graph.post(
            f"/identity/authenticationEventsFlows/{flow['id']}/conditions/applications/includeApplications",
            {"@odata.type": "#microsoft.graph.authenticationConditionApplication", "appId": app_id},
        )
    return flow


def main() -> None:
    graph = GraphClient(AzureCliCredential(tenant_id=EXTERNAL_TENANT_ID))
    app = ensure_app(graph)
    sp = ensure_service_principal(graph, app["appId"])
    ensure_sign_in_consent(graph, sp["id"])
    try:
        flow = ensure_user_flow(graph, app["appId"])
    except GraphError as error:
        raise SystemExit(f"User flow setup failed: {error}") from error
    print(json.dumps({"clientId": app["appId"], "userFlowId": flow["id"]}, indent=2))


if __name__ == "__main__":
    main()
