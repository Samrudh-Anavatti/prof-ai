import hashlib
import json

import pytest

from prof_ai.content.manifest import InvalidSlugError, Licence, LicenceType
from prof_ai.content.pdf import InvalidPdfError
from prof_ai.content.store import BookExistsError, BookNotFoundError

from .conftest import FIXED_NOW, make_pdf

OWN = Licence(type=LicenceType.OWN, notes="Written by Sam")


def add(store, pdf=None, slug="maths-9", **overrides):
    fields = {"title": "Maths 9", "subject": "maths", "grades": [9], "licence": OWN}
    fields.update(overrides)
    return store.add_book(pdf or make_pdf(3), slug=slug, **fields)


def test_add_book_writes_source_and_manifest_to_contract_paths(store, backend):
    pdf = make_pdf(3)
    add(store, pdf, curriculum="national-ks3")

    source, source_type = backend.blobs[("sources", "books/maths-9/original.pdf")]
    assert source == pdf
    assert source_type == "application/pdf"

    raw, manifest_type = backend.blobs[("content", "books/maths-9/manifest.json")]
    assert manifest_type == "application/json"
    manifest = json.loads(raw)
    assert manifest["schema_version"] == 1
    assert manifest["slug"] == "maths-9"
    assert manifest["subject"] == "maths"
    assert manifest["grades"] == [9]
    assert manifest["curriculum"] == "national-ks3"
    assert manifest["licence"] == {"type": "own", "notes": "Written by Sam"}
    assert manifest["source_blob"] == "sources/books/maths-9/original.pdf"
    assert manifest["sha256"] == hashlib.sha256(pdf).hexdigest()
    assert manifest["page_count"] == 3
    assert manifest["uploaded_at"].startswith(FIXED_NOW.isoformat()[:19])


def test_chapters_come_from_top_level_outline(store):
    pdf = make_pdf(10, outline=[("Chapter 2: Algebra", 4), ("Chapter 1: Number", 0)])
    manifest = add(store, pdf)
    assert [(c.title, c.start_page, c.end_page, c.status) for c in manifest.chapters] == [
        ("Chapter 1: Number", 1, 4, "not_extracted"),
        ("Chapter 2: Algebra", 5, 10, "not_extracted"),
    ]


def test_pdf_without_outline_has_no_chapters(store):
    assert add(store, make_pdf(2)).chapters == []


def test_non_pdf_is_rejected_and_nothing_is_written(store, backend):
    with pytest.raises(InvalidPdfError):
        add(store, b"not a pdf at all")
    assert backend.blobs == {}


@pytest.mark.parametrize("slug", ["Maths", "../escape", "maths_9", "-maths", "a--b", "x" * 65])
def test_invalid_slugs_are_rejected(store, backend, slug):
    with pytest.raises(InvalidSlugError):
        add(store, slug=slug)
    assert backend.blobs == {}


def test_existing_book_is_not_overwritten_without_replace(store):
    add(store, make_pdf(2))
    with pytest.raises(BookExistsError):
        add(store, make_pdf(5))
    assert store.get_book("maths-9").page_count == 2

    add(store, make_pdf(5), replace=True)
    assert store.get_book("maths-9").page_count == 5


def test_list_and_get_books(store):
    add(store, slug="maths-9")
    add(store, slug="physics-10", subject="physics", grades=[10, 11])
    assert [book.slug for book in store.list_books()] == ["maths-9", "physics-10"]
    assert store.get_book("physics-10").grades == [10, 11]


def test_missing_book_raises_not_found(store):
    with pytest.raises(BookNotFoundError):
        store.get_book("nope")
