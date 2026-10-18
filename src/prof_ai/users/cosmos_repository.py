from azure.core.credentials import TokenCredential
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

from prof_ai.users.models import AuditEvent, User

DATABASE = "prof-ai"


class CosmosUserRepository:
    def __init__(self, endpoint: str, credential: TokenCredential | None = None):
        client = CosmosClient(endpoint, credential=credential or DefaultAzureCredential())
        database = client.get_database_client(DATABASE)
        self._users = database.get_container_client("users")
        self._audit = database.get_container_client("audit")

    def get(self, user_id: str) -> User | None:
        try:
            return User.model_validate(self._users.read_item(user_id, partition_key=user_id))
        except CosmosResourceNotFoundError:
            return None

    def find_by_email(self, email: str) -> User | None:
        items = self._users.query_items(
            "SELECT * FROM c WHERE c.email = @email",
            parameters=[{"name": "@email", "value": email}],
            enable_cross_partition_query=True,
        )
        return next((User.model_validate(item) for item in items), None)

    def list(self) -> list[User]:
        items = self._users.query_items("SELECT * FROM c", enable_cross_partition_query=True)
        return sorted((User.model_validate(item) for item in items), key=lambda u: u.email)

    def save(self, user: User) -> None:
        self._users.upsert_item(user.model_dump(mode="json"))

    def delete(self, user_id: str) -> None:
        try:
            self._users.delete_item(user_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            pass

    def record(self, event: AuditEvent) -> None:
        self._audit.create_item(event.model_dump(mode="json"))
