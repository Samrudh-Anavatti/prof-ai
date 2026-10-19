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

    def delete_conversation(self, user_id: str, conversation_id: str) -> None:
        try:
            self._conversations.delete_item(conversation_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            pass

    def cost_used(self, user_id: str, day: date) -> int:
        try:
            item = self._usage.read_item(usage_id(user_id, day), partition_key=user_id)
        except CosmosResourceNotFoundError:
            return 0
        return int(item.get("cost_micro_usd", 0))

    def cost_used_by_everyone(self, day: date) -> int:
        items = self._usage.query_items(
            "SELECT VALUE SUM(c.cost_micro_usd) FROM c "
            "WHERE c.date = @date AND IS_NUMBER(c.cost_micro_usd)",
            parameters=[{"name": "@date", "value": day.isoformat()}],
            enable_cross_partition_query=True,
        )
        return int(next(iter(items), 0) or 0)

    def delete_user_data(self, user_id: str) -> None:
        for container in (self._conversations, self._usage):
            ids = container.query_items(
                "SELECT VALUE c.id FROM c", partition_key=user_id, max_item_count=100
            )
            for item_id in list(ids):
                container.delete_item(item_id, partition_key=user_id)

    def add_usage(self, user_id: str, day: date, tokens: int, cost_micro_usd: int) -> None:
        item_id = usage_id(user_id, day)
        try:
            self._usage.patch_item(
                item_id,
                partition_key=user_id,
                patch_operations=[
                    {"op": "incr", "path": "/tokens", "value": tokens},
                    {"op": "incr", "path": "/cost_micro_usd", "value": cost_micro_usd},
                ],
            )
        except CosmosResourceNotFoundError:
            self._usage.upsert_item(
                {
                    "id": item_id,
                    "user_id": user_id,
                    "date": day.isoformat(),
                    "tokens": tokens,
                    "cost_micro_usd": cost_micro_usd,
                }
            )
