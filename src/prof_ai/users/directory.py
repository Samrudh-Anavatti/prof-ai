from typing import Protocol

from prof_ai.graph import GraphClient


class Directory(Protocol):
    def set_enabled(self, user_id: str, enabled: bool) -> None: ...

    def delete_user(self, user_id: str) -> None: ...


class ExternalIdDirectory:
    """Sign-in accounts in the Entra External ID tenant; people create their own by signing up."""

    def __init__(self, graph: GraphClient):
        self._graph = graph

    def set_enabled(self, user_id: str, enabled: bool) -> None:
        self._graph.patch(f"/users/{user_id}", {"accountEnabled": enabled})

    def delete_user(self, user_id: str) -> None:
        self._graph.delete(f"/users/{user_id}")
