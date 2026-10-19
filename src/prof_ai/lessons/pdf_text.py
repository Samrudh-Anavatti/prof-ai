from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader

from prof_ai.chat.context import estimate_tokens

MAX_LESSON_PDF_BYTES = 10 * 1024 * 1024
MAX_LESSON_PDF_PAGES = 60


class LessonPdfError(ValueError):
    pass


@dataclass(frozen=True)
class PageText:
    number: int
    text: str
    tokens: int


def extract_pages(data: bytes) -> list[PageText]:
    """Text of each page, for the tutor to pick from. Nothing is stored."""
    if not data.startswith(b"%PDF-"):
        raise LessonPdfError("That file isn't a PDF.")
    if len(data) > MAX_LESSON_PDF_BYTES:
        raise LessonPdfError(
            f"The PDF is over {MAX_LESSON_PDF_BYTES // (1024 * 1024)} MB. Upload just the pages "
            "for this lesson."
        )
    try:
        reader = PdfReader(BytesIO(data))
        if len(reader.pages) > MAX_LESSON_PDF_PAGES:
            raise LessonPdfError(
                f"The PDF has {len(reader.pages)} pages; the limit is {MAX_LESSON_PDF_PAGES}. "
                "Split out the pages for this lesson first."
            )
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append(PageText(number=number, text=text, tokens=estimate_tokens(text)))
    except LessonPdfError:
        raise
    except Exception as error:
        # pypdf raises a variety of errors on damaged files; all mean the same to a tutor.
        raise LessonPdfError(
            "The PDF couldn't be read. Try saving it again or exporting it."
        ) from error
    return pages
