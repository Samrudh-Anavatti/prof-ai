import pytest

from prof_ai.chat.context import LAYER_CAPS, Layer
from prof_ai.lessons.pdf_text import MAX_LESSON_PDF_PAGES

from .conftest import as_upload, make_text_pdf


def test_tutor_gets_the_text_of_each_page_with_its_size(h):
    pdf = make_text_pdf(["Ratios compare two amounts.", "Exercise 1: simplify 6:9."])
    response = h.extract("sam", as_upload(pdf))
    assert response.status_code == 200
    body = response.json()
    assert [(p["number"], p["text"]) for p in body["pages"]] == [
        (1, "Ratios compare two amounts."),
        (2, "Exercise 1: simplify 6:9."),
    ]
    assert body["pages"][0]["tokens"] == 9
    assert body["max_lesson_tokens"] == LAYER_CAPS[Layer.LESSON]


def test_students_cannot_extract(h):
    assert h.extract("alex", as_upload(make_text_pdf(["x"]))).status_code == 403


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"filename": "a.pdf", "pdf_base64": "bm90IGEgcGRm"}, "isn't a PDF"),
        ({"filename": "a.pdf", "pdf_base64": "%%%not base64%%%"}, "isn't a PDF"),
        ({"filename": "a.pdf", "pdf_base64": "JVBERi0xLjQKZ2FyYmFnZQ=="}, "couldn't be read"),
    ],
)
def test_bad_files_get_a_clear_400(h, body, message):
    response = h.extract("sam", body)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_too_many_pages_is_refused(h):
    pdf = make_text_pdf(["page"] * (MAX_LESSON_PDF_PAGES + 1))
    response = h.extract("sam", as_upload(pdf))
    assert response.status_code == 400
    assert "Split out" in response.json()["detail"]


def test_an_oversized_request_is_refused_before_it_is_read(h):
    response = h.client.post(
        "/api/lessons/extract",
        content=b"{}",
        headers={
            **h.as_user("sam"),
            "content-type": "application/json",
            "content-length": str(20 * 1024 * 1024),
        },
    )
    assert response.status_code == 413


def test_other_api_bodies_are_limited_to_a_megabyte(h):
    response = h.client.put(
        "/api/teaching-style",
        content=b"{}",
        headers={
            **h.as_user("sam"),
            "content-type": "application/json",
            "content-length": str(2 * 1024 * 1024),
        },
    )
    assert response.status_code == 413
