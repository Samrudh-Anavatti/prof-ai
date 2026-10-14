from collections.abc import Iterable
from datetime import UTC, datetime
from io import BytesIO

import pytest
from pypdf import PdfWriter

from prof_ai.content.store import ContentStore

FIXED_NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


class InMemoryBlobBackend:
    def __init__(self) -> None:
        self.blobs: dict[tuple[str, str], tuple[bytes, str]] = {}

    def upload(self, container: str, name: str, data: bytes, content_type: str) -> None:
        self.blobs[(container, name)] = (data, content_type)

    def download(self, container: str, name: str) -> bytes:
        return self.blobs[(container, name)][0]

    def exists(self, container: str, name: str) -> bool:
        return (container, name) in self.blobs

    def list_names(self, container: str, prefix: str) -> Iterable[str]:
        return [name for (c, name) in self.blobs if c == container and name.startswith(prefix)]


def make_pdf(pages: int, outline: list[tuple[str, int]] | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    for title, page_index in outline or []:
        writer.add_outline_item(title, page_index)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def backend() -> InMemoryBlobBackend:
    return InMemoryBlobBackend()


@pytest.fixture
def store(backend: InMemoryBlobBackend) -> ContentStore:
    return ContentStore(backend, clock=lambda: FIXED_NOW)
