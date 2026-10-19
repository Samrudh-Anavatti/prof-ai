import base64
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from tests.tutor_chat.conftest import Harness


def make_text_pdf(page_texts: list[str]) -> bytes:
    """A real PDF whose pages carry these lines of text, so extraction can be tested."""
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    for text in page_texts:
        page = writer.add_blank_page(width=400, height=200)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode("latin-1"))
        page.replace_contents(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def as_upload(data: bytes, filename: str = "chapter.pdf") -> dict:
    return {"filename": filename, "pdf_base64": base64.b64encode(data).decode("ascii")}


class LessonHarness(Harness):
    def chats_url(self, student_id: str) -> str:
        return f"/api/students/{student_id}/chats"

    def create(self, actor: str, student_id: str, lesson: dict, licence: bool = True):
        return self.client.post(
            self.chats_url(student_id),
            json={"lesson": lesson, "licence_confirmed": licence},
            headers=self.as_user(actor),
        )

    def list(self, actor: str, student_id: str):
        return self.client.get(self.chats_url(student_id), headers=self.as_user(actor))

    def delete(self, actor: str, student_id: str, conversation_id: str):
        return self.client.delete(
            f"{self.chats_url(student_id)}/{conversation_id}", headers=self.as_user(actor)
        )

    def extract(self, actor: str, body: dict):
        return self.client.post("/api/lessons/extract", json=body, headers=self.as_user(actor))


RATIOS = {
    "title": "Ratios",
    "topics": ["Simplifying ratios", "Sharing in a ratio"],
    "notes": "Alex mixes up the order of the parts.",
    "material": "A ratio compares quantities. Simplify by dividing by the HCF.",
    "sources": [{"filename": "chapter.pdf", "pages": [1, 2]}],
}


@pytest.fixture
def h() -> LessonHarness:
    return LessonHarness()
