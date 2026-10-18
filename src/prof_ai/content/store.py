import hashlib
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Protocol

from prof_ai.content.manifest import BookManifest, Licence, validate_slug
from prof_ai.content.pdf import inspect_pdf

SOURCES_CONTAINER = "sources"
CONTENT_CONTAINER = "content"


class BlobBackend(Protocol):
    def upload(self, container: str, name: str, data: bytes, content_type: str) -> None: ...

    def download(self, container: str, name: str) -> bytes: ...

    def exists(self, container: str, name: str) -> bool: ...

    def list_names(self, container: str, prefix: str) -> Iterable[str]: ...

    def delete(self, container: str, name: str) -> None: ...


class BookExistsError(Exception):
    pass


class BookNotFoundError(Exception):
    pass


def book_source_path(slug: str) -> str:
    return f"books/{slug}/original.pdf"


def book_manifest_path(slug: str) -> str:
    return f"books/{slug}/manifest.json"


class ContentStore:
    def __init__(
        self, backend: BlobBackend, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ):
        self._backend = backend
        self._clock = clock

    def add_book(
        self,
        pdf: bytes,
        *,
        slug: str,
        title: str,
        subject: str,
        grades: list[int],
        licence: Licence,
        curriculum: str = "",
        replace: bool = False,
    ) -> BookManifest:
        validate_slug(slug)
        if not replace and self._backend.exists(CONTENT_CONTAINER, book_manifest_path(slug)):
            raise BookExistsError(f"Book {slug!r} already exists. Pass replace to overwrite it.")
        info = inspect_pdf(pdf)
        manifest = BookManifest(
            slug=slug,
            title=title,
            subject=subject,
            grades=grades,
            curriculum=curriculum,
            licence=licence,
            source_blob=f"{SOURCES_CONTAINER}/{book_source_path(slug)}",
            sha256=hashlib.sha256(pdf).hexdigest(),
            page_count=info.page_count,
            uploaded_at=self._clock(),
            chapters=info.chapters,
        )
        # Source first, so a manifest never points at a missing original.
        self._backend.upload(SOURCES_CONTAINER, book_source_path(slug), pdf, "application/pdf")
        self._backend.upload(
            CONTENT_CONTAINER,
            book_manifest_path(slug),
            manifest.model_dump_json(indent=2).encode(),
            "application/json",
        )
        return manifest

    def get_book(self, slug: str) -> BookManifest:
        validate_slug(slug)
        path = book_manifest_path(slug)
        if not self._backend.exists(CONTENT_CONTAINER, path):
            raise BookNotFoundError(f"Book {slug!r} not found.")
        return BookManifest.model_validate_json(self._backend.download(CONTENT_CONTAINER, path))

    def list_books(self) -> list[BookManifest]:
        names = self._backend.list_names(CONTENT_CONTAINER, "books/")
        return [
            BookManifest.model_validate_json(self._backend.download(CONTENT_CONTAINER, name))
            for name in sorted(names)
            if name.endswith("/manifest.json")
        ]
