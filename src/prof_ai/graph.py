from typing import Any

import requests
from azure.core.credentials import TokenCredential

GRAPH_URL = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"


class GraphError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"Microsoft Graph returned {status}: {message}")
        self.status = status


class GraphClient:
    def __init__(self, credential: TokenCredential, session: requests.Session | None = None):
        self._credential = credential
        self._session = session or requests.Session()

    def request(self, method: str, path: str, json: Any = None) -> Any:
        token = self._credential.get_token(GRAPH_SCOPE).token
        response = self._session.request(
            method,
            f"{GRAPH_URL}{path}",
            json=json,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if response.status_code >= 400:
            raise GraphError(response.status_code, response.text[:500])
        return response.json() if response.content else None

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, json: Any) -> Any:
        return self.request("POST", path, json)

    def patch(self, path: str, json: Any) -> Any:
        return self.request("PATCH", path, json)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)
