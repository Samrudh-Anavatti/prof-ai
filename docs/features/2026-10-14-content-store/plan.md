# Plan: Content store basics

- **Owner:** sam
- **Branch:** `sam/content-store`
- **Date:** 2026-10-14

## Goal
Let tutors put textbooks into the content store now, with the metadata later features need, without paying for any indexing or AI processing up front. This is the first slice of the folder-structured content store in `docs/product/architecture.md`.

## Approach
- **A `prof` CLI** (`prof content add-book | list | show`), installed with `pip install -e .`. It authenticates as the tutor with `DefaultAzureCredential` (`az login`). No keys.
- **Blob layout:**
  - `sources/books/<slug>/original.pdf`: the untouched upload. Only tutors can read it; the app identity has no access to `sources`.
  - `content/books/<slug>/manifest.json`: book metadata, which the app can read.
- **Manifest** (a pydantic model, `schema_version: 1`):
  - slug, title, subject, grades, curriculum
  - licence type and notes
  - source blob path, SHA-256, page count, upload time
  - chapters (title, start page, end page, `status: "not_extracted"`)
- **Chapters** come from the PDF's own outline (bookmarks) when it has one, which is free and local. Otherwise the list is empty, to be set later. Text extraction is a later feature that runs lazily when a chapter is first assigned.
- **`ContentStore`** sits on a small `BlobBackend` protocol, with an Azure implementation and an in-memory one for tests. Later features read books through `ContentStore`, not raw blob paths.

## Risks
- **Licence breach (R12):** `--licence-type` is required: `own`, `licensed`, `open` or `unverified`. Later features must not show `unverified` books to students. Licence notes are stored alongside.
- **Path traversal / messy blob names:** slugs must match `^[a-z0-9]+(-[a-z0-9]+)*$`, max 64 characters.
- **Accidental overwrite:** refused unless `--replace` is passed. Blob soft delete (14 days) is the backstop.
- **Wrong or hostile file:** only files with a PDF header are accepted, up to 300 MB, parsed locally with pypdf. Uploads come from trusted tutors only.
- **Data:** no student data is involved. Textbooks are never committed to the repo; tests generate blank synthetic PDFs.
- **Cost:** a blob upload costs pennies. No AI or indexing calls.

## Files / modules touched
- `src/prof_ai/content/` (`manifest.py`, `store.py`, `azure_backend.py`, `pdf.py`), `src/prof_ai/cli.py`
- `pyproject.toml` (build system + `prof` script), `requirements*.txt`, `.env.example`, `CLAUDE.md`

## Contracts added or changed
- The blob layout above, and the `BookManifest` JSON schema (`schema_version: 1`).
- `ContentStore.add_book / get_book / list_books`.
- `STORAGE_ACCOUNT_URL` env var (already set in production).

## Tests to add
`tests/content_store/`:
- the manifest written to the right path with the right fields
- the original stored under `sources/`
- chapters detected from the outline
- non-PDFs rejected
- bad slugs rejected
- overwrite refused without `replace`
- listing and reading books back
- CLI `add-book` / `list` working end to end against the in-memory backend

## Open questions
- How do curricula and worksheets fit the layout? That comes in a later slice, once Sam has looked at real material.
