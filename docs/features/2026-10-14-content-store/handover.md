# Handover: Content store basics

- **Owner:** sam
- **PR:** https://github.com/Samrudh-Anavatti/prof-ai/pull/4
- **Merged:** 2026-10-14

## What was built
- **The `prof` CLI** (`src/prof_ai/cli.py`): `prof content add-book | list | show`. It authenticates with your `az login` through `DefaultAzureCredential`. No keys.
- **`ContentStore`** (`src/prof_ai/content/store.py`): add, get and list books on a `BlobBackend` protocol. `AzureBlobBackend` is the real implementation; the tests use an in-memory one.
- **`BookManifest`** (`src/prof_ai/content/manifest.py`): a pydantic model, `schema_version: 1`.
- **`inspect_pdf`** (`src/prof_ai/content/pdf.py`): checks the PDF header and the 300 MB limit, counts pages, and reads chapters from the PDF's top-level outline (bookmarks).
- **Packaging:** the repo is now an installable package (`pip install -e .`, done by `requirements-dev.txt`), which provides the `prof` command.
- **Verified live on 2026-10-14:** uploaded, listed and showed a synthetic PDF against `stprofaicjzzqh`, then deleted it. The store is empty and ready for real books.

Built as planned.

## How to run / use it
```bash
az login
.venv/Scripts/prof content add-book path/to/book.pdf \
  --slug maths-9-core --title "Core Maths 9" --subject maths --grades 9,10 \
  --curriculum <curriculum-slug> --licence-type licensed --licence-notes "Publisher licence #123"
.venv/Scripts/prof content list
.venv/Scripts/prof content show maths-9-core
```

- **Licence type** (`--licence-type`) is required: `own`, `licensed`, `open` or `unverified`. Use `unverified` if you're not sure; those books will be kept away from students.
- **Re-uploading** an existing slug is refused unless you pass `--replace`.

## Contracts other code can rely on
- **Blob layout:**
  - `sources/books/<slug>/original.pdf`: original, tutors only. The web app's identity can't read `sources`.
  - `content/books/<slug>/manifest.json`: the `BookManifest` JSON.
- **`BookManifest` v1 fields:**
  - `slug`, `title`, `subject`, `grades`, `curriculum`
  - `licence {type, notes}`
  - `source_blob`, `sha256`, `page_count`, `uploaded_at`
  - `chapters [{title, start_page, end_page, status: "not_extracted"}]`

  Pages are 1-based and inclusive.
- **Slugs** match `^[a-z0-9]+(-[a-z0-9]+)*$`, max 64 characters.
- **Read books through `ContentStore`**, not raw blob paths, so the layout can change in one place.

## Tests added
`tests/content_store/`:
- the manifest and source written to the contract paths with the right fields
- chapters from the outline (sorted, end pages computed, nested entries ignored)
- non-PDFs and invalid slugs rejected with nothing written
- no overwrite without `replace`
- list and get, and not-found
- the CLI `add-book` / `list` / `show` flow, licence type required, errors exit 1 with a message

## Known issues / TODOs
- **Chapter detection** depends on the PDF having bookmarks. Many scanned books don't. There's no command to set or edit chapters yet; add one (e.g. `prof content set-chapters <slug> chapters.json`) when Sam hits this.
- **Top-level outline entries** include front matter ("Contents", "Index") as "chapters". Harmless for now; tidy up when chapters get assigned.
- **The whole PDF is read into memory** on upload. Fine at 300 MB on a dev machine.
- **Curricula and worksheets** aren't in the store yet.
- **`unverified` licences** aren't enforced yet. The assignment feature must block them.

## For the other dev
Once you're in the tenant and in `tutorPrincipalIds`, `az login` and the CLI work for you too. Never commit textbooks or other content into the repo: it's public and copyrighted.
