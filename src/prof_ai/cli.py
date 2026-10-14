import argparse
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from prof_ai.content.manifest import InvalidSlugError, Licence, LicenceType
from prof_ai.content.pdf import InvalidPdfError
from prof_ai.content.store import BookExistsError, BookNotFoundError, ContentStore

StoreFactory = Callable[[], ContentStore]


def azure_store() -> ContentStore:
    from prof_ai.content.azure_backend import AzureBlobBackend

    account_url = os.environ.get("STORAGE_ACCOUNT_URL")
    if not account_url:
        raise SystemExit("Set STORAGE_ACCOUNT_URL (see .env.example).")
    return ContentStore(AzureBlobBackend(account_url))


def parse_grades(value: str) -> list[int]:
    try:
        return [int(grade) for grade in value.split(",") if grade.strip()]
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Grades must be comma-separated numbers, e.g. 9,10"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prof", description="Prof AI tutor tools.")
    groups = parser.add_subparsers(dest="group", required=True)

    content = groups.add_parser("content", help="Manage the content store.")
    commands = content.add_subparsers(dest="command", required=True)

    add_book = commands.add_parser("add-book", help="Upload a textbook PDF.")
    add_book.add_argument("pdf", type=Path)
    add_book.add_argument("--slug", required=True, help="e.g. maths-year-9-core")
    add_book.add_argument("--title", required=True)
    add_book.add_argument("--subject", required=True)
    add_book.add_argument("--grades", required=True, type=parse_grades, help="e.g. 9,10")
    add_book.add_argument("--curriculum", default="")
    add_book.add_argument(
        "--licence-type", required=True, choices=[licence.value for licence in LicenceType]
    )
    add_book.add_argument("--licence-notes", default="")
    add_book.add_argument("--replace", action="store_true", help="Overwrite an existing book.")

    commands.add_parser("list", help="List books.")

    show = commands.add_parser("show", help="Print a book's manifest.")
    show.add_argument("slug")
    return parser


def run(args: argparse.Namespace, store: ContentStore) -> None:
    if args.command == "add-book":
        manifest = store.add_book(
            args.pdf.read_bytes(),
            slug=args.slug,
            title=args.title,
            subject=args.subject,
            grades=args.grades,
            curriculum=args.curriculum,
            licence=Licence(type=args.licence_type, notes=args.licence_notes),
            replace=args.replace,
        )
        print(
            f"Added {manifest.slug}: {manifest.page_count} pages, "
            f"{len(manifest.chapters)} chapters from the PDF outline, "
            f"licence {manifest.licence.type}."
        )
    elif args.command == "list":
        for book in store.list_books():
            grades = ",".join(str(grade) for grade in book.grades)
            print(
                f"{book.slug}\t{book.title}\t{book.subject}\tgrades {grades}\t"
                f"{book.page_count}p\t{len(book.chapters)} chapters\t{book.licence.type}"
            )
    elif args.command == "show":
        print(store.get_book(args.slug).model_dump_json(indent=2))


def main(argv: Sequence[str] | None = None, store_factory: StoreFactory = azure_store) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        run(args, store_factory())
    except (
        BookExistsError,
        BookNotFoundError,
        InvalidPdfError,
        InvalidSlugError,
        ValidationError,
        FileNotFoundError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
