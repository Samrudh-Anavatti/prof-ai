import secrets
from typing import Protocol

from prof_ai.graph import GraphClient


class Directory(Protocol):
    def find_user_id(self, email: str) -> str | None: ...

    def create_user(self, email: str, display_name: str) -> str: ...

    def set_enabled(self, user_id: str, enabled: bool) -> None: ...


class ExternalIdDirectory:
    """Accounts in the Entra External ID tenant; users sign in with email one-time passcodes."""

    def __init__(self, graph: GraphClient, tenant_domain: str):
        self._graph = graph
        self._tenant_domain = tenant_domain

    def find_user_id(self, email: str) -> str | None:
        query = (
            "/users?$select=id&$filter=identities/any(i:i/issuer eq "
            f"'{self._tenant_domain}' and i/issuerAssignedId eq '{_quote(email)}')"
        )
        users = self._graph.get(query)["value"]
        return users[0]["id"] if users else None

    def create_user(self, email: str, display_name: str) -> str:
        user = self._graph.post(
            "/users",
            {
                "displayName": display_name,
                "accountEnabled": True,
                "mail": email,
                "identities": [
                    {
                        "signInType": "emailAddress",
                        "issuer": self._tenant_domain,
                        "issuerAssignedId": email,
                    }
                ],
                # Required by Graph but never used: sign-in is by email one-time passcode.
                "passwordProfile": {
                    "password": secrets.token_urlsafe(48),
                    "forceChangePasswordNextSignIn": False,
                },
                "passwordPolicies": "DisablePasswordExpiration",
            },
        )
        return user["id"]

    def set_enabled(self, user_id: str, enabled: bool) -> None:
        self._graph.patch(f"/users/{user_id}", {"accountEnabled": enabled})


def _quote(value: str) -> str:
    return value.replace("'", "''")
