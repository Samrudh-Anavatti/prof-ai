from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from prof_ai.content.manifest import Chapter

MAX_PDF_BYTES = 300 * 1024 * 1024


class InvalidPdfError(ValueError):
    pass


@dataclass(frozen=True)
class PdfInfo:
    page_count: int
    chapters: list[Chapter]


def inspect_pdf(data: bytes) -> PdfInfo:
    if not data.startswith(b"%PDF-"):
        raise InvalidPdfError("File is not a PDF.")
    if len(data) > MAX_PDF_BYTES:
        raise InvalidPdfError(f"PDF is larger than {MAX_PDF_BYTES // (1024 * 1024)} MB.")
    try:
        reader = PdfReader(BytesIO(data))
        page_count = len(reader.pages)
        chapters = _chapters_from_outline(reader, page_count)
    except PdfReadError as error:
        raise InvalidPdfError(f"PDF could not be read: {error}") from error
    if page_count == 0:
        raise InvalidPdfError("PDF has no pages.")
    return PdfInfo(page_count=page_count, chapters=chapters)


def _chapters_from_outline(reader: PdfReader, page_count: int) -> list[Chapter]:
    starts: dict[int, str] = {}
    # Nested lists in the outline are sub-sections; only top-level entries count as chapters.
    for item in reader.outline:
        if isinstance(item, list):
            continue
        try:
            page = reader.get_destination_page_number(item) + 1
        except (PdfReadError, KeyError, TypeError, ValueError):
            continue
        if page >= 1:
            starts.setdefault(page, str(item.title).strip())
    ordered = sorted(starts.items())
    chapters = []
    for index, (start, title) in enumerate(ordered):
        next_start = ordered[index + 1][0] if index + 1 < len(ordered) else page_count + 1
        chapters.append(Chapter(title=title, start_page=start, end_page=next_start - 1))
    return chapters
