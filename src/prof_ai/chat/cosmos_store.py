from datetime import date

from azure.core.credentials import TokenCredential
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

from prof_ai.chat.models import Conversation
from prof_ai.users.cosmos_repository import DATABASE


def usage_id(user_id: str, day: date) -> str:
    return f"{user_id}:{day.isoformat()}"


class CosmosChatStore:
    def __init__(self, endpoint: str, credential: TokenCredential | None = None):
        client = CosmosClient(endpoint, credential=credential or DefaultAzureCredential())
        database = client.get_database_client(DATABASE)
        self._conversations = database.get_container_client("conversations")
        self._usage = database.get_container_client("usage")

    def list_conversations(self, user_id: str) -> list[Conversation]:
        items = self._conversations.query_items(
            "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.updated_at DESC",
            parameters=[{"name": "@user_id", "value": user_id}],
            partition_key=user_id,
        )
        return [Conversation.model_validate(item) for item in items]

    def get_conversation(self, user_id: str, conversation_id: str) -> Conversation | None:
        try:
            item = self._conversations.read_item(conversation_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return None
        return Conversation.model_validate(item)

    def save_conversation(self, conversation: Conversation) -> None:
        self._conversations.upsert_item(conversation.model_dump(mode="json"))

    def tokens_used(self, user_id: str, day: date) -> int:
        try:
            item = self._usage.read_item(usage_id(user_id, day), partition_key=user_id)
        except CosmosResourceNotFoundError:
            return 0
        return int(item["tokens"])

    def tokens_used_by_everyone(self, day: date) -> int:
        items = self._usage.query_items(
            "SELECT VALUE SUM(c.tokens) FROM c WHERE c.date = @date",
            parameters=[{"name": "@date", "value": day.isoformat()}],
            enable_cross_partition_query=True,
        )
        return int(next(iter(items), 0) or 0)

    def add_tokens(self, user_id: str, day: date, tokens: int) -> None:
        item_id = usage_id(user_id, day)
        try:
            self._usage.patch_item(
                item_id,
                partition_key=user_id,
                patch_operations=[{"op": "incr", "path": "/tokens", "value": tokens}],
            )
        except CosmosResourceNotFoundError:
            self._usage.upsert_item(
                {"id": item_id, "user_id": user_id, "date": day.isoformat(), "tokens": tokens}
            )
