import json

import pytest

from prof_ai.cli import main

from .conftest import make_pdf


@pytest.fixture
def run_cli(store):
    def run(*argv: str) -> int:
        return main(list(argv), store_factory=lambda: store)

    return run


def test_add_book_list_and_show(run_cli, tmp_path, capsys):
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(make_pdf(4, outline=[("Chapter 1", 0)]))

    assert (
        run_cli(
            "content", "add-book", str(pdf_path),
            "--slug", "maths-9", "--title", "Maths 9", "--subject", "maths",
            "--grades", "9,10", "--licence-type", "own",
        )
        == 0
    )  # fmt: skip
    assert "Added maths-9: 4 pages, 1 chapters" in capsys.readouterr().out

    assert run_cli("content", "list") == 0
    assert capsys.readouterr().out.startswith("maths-9\tMaths 9\tmaths\tgrades 9,10")

    assert run_cli("content", "show", "maths-9") == 0
    assert json.loads(capsys.readouterr().out)["grades"] == [9, 10]


def test_licence_type_is_required(run_cli, tmp_path):
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(make_pdf(1))
    with pytest.raises(SystemExit):
        run_cli(
            "content", "add-book", str(pdf_path),
            "--slug", "maths-9", "--title", "Maths 9", "--subject", "maths", "--grades", "9",
        )  # fmt: skip


def test_errors_exit_non_zero_with_message(run_cli, tmp_path, capsys):
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    code = run_cli(
        "content", "add-book", str(bad),
        "--slug", "maths-9", "--title", "Maths 9", "--subject", "maths",
        "--grades", "9", "--licence-type", "own",
    )  # fmt: skip
    assert code == 1
    assert "Error: File is not a PDF." in capsys.readouterr().err
