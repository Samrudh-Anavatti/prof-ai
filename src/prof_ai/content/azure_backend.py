from collections.abc import Iterable

from azure.core.credentials import TokenCredential
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings


class AzureBlobBackend:
    def __init__(self, account_url: str, credential: TokenCredential | None = None):
        self._service = BlobServiceClient(
            account_url, credential=credential or DefaultAzureCredential()
        )

    def upload(self, container: str, name: str, data: bytes, content_type: str) -> None:
        self._service.get_blob_client(container, name).upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
            max_concurrency=4,
        )

    def download(self, container: str, name: str) -> bytes:
        return self._service.get_blob_client(container, name).download_blob().readall()

    def delete(self, container: str, name: str) -> None:
        self._service.get_blob_client(container, name).delete_blob(delete_snapshots="include")

    def exists(self, container: str, name: str) -> bool:
        return self._service.get_blob_client(container, name).exists()

    def list_names(self, container: str, prefix: str) -> Iterable[str]:
        return self._service.get_container_client(container).list_blob_names(
            name_starts_with=prefix
        )
