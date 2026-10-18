import argparse
import base64
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from prof_ai.content.manifest import InvalidSlugError, Licence, LicenceType
from prof_ai.content.pdf import InvalidPdfError
from prof_ai.content.store import BookExistsError, BookNotFoundError, ContentStore
from prof_ai.graph import GraphError
from prof_ai.users.admin import UserAdmin, UserAdminError
from prof_ai.users.models import Role

StoreFactory = Callable[[], ContentStore]
AdminFactory = Callable[[], UserAdmin]


def azure_store() -> ContentStore:
    from prof_ai.content.azure_backend import AzureBlobBackend

    return ContentStore(AzureBlobBackend(require_env("STORAGE_ACCOUNT_URL")))


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Set {name} (see .env.example).")
    return value


def signed_in_actor(credential) -> str:
    token = credential.get_token("https://management.azure.com/.default").token
    payload = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    return claims.get("email") or claims.get("upn") or claims.get("unique_name") or claims["oid"]


def azure_user_admin() -> UserAdmin:
    from azure.identity import AzureCliCredential

    from prof_ai.graph import GraphClient
    from prof_ai.users.cosmos_repository import CosmosUserRepository
    from prof_ai.users.directory import ExternalIdDirectory

    directory = ExternalIdDirectory(
        GraphClient(AzureCliCredential(tenant_id=require_env("EXTERNAL_TENANT_ID"))),
        require_env("EXTERNAL_TENANT_DOMAIN"),
    )
    return UserAdmin(
        CosmosUserRepository(require_env("COSMOS_ENDPOINT")),
        directory,
        actor=signed_in_actor(AzureCliCredential()),
    )


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

    users = groups.add_parser("users", help="Manage tutor and student accounts.")
    user_commands = users.add_subparsers(dest="command", required=True)

    add_user = user_commands.add_parser("add", help="Invite a tutor or student.")
    add_user.add_argument("--email", required=True)
    add_user.add_argument("--name", required=True, help="Display name (first name is enough).")
    add_user.add_argument("--role", required=True, choices=[role.value for role in Role])
    add_user.add_argument("--tutor", help="Tutor's email (students only).")

    user_commands.add_parser("list", help="List accounts.")

    lock = user_commands.add_parser("lock", help="Lock an account immediately.")
    lock.add_argument("email")
    lock.add_argument("--reason", required=True)

    unlock = user_commands.add_parser("unlock", help="Unlock an account.")
    unlock.add_argument("email")
    unlock.add_argument("--reason", default="")
    return parser


def run_users(args: argparse.Namespace, admin: UserAdmin) -> None:
    if args.command == "add":
        user = admin.add(args.email, args.name, Role(args.role), args.tutor)
        print(f"Added {user.role} {user.email} ({user.id}).")
    elif args.command == "list":
        for user in admin.list():
            print(
                f"{user.email}	{user.display_name}	{user.role}	{user.status}	{user.id}"
            )
    elif args.command == "lock":
        print(f"Locked {admin.lock(args.email, args.reason).email}.")
    elif args.command == "unlock":
        print(f"Unlocked {admin.unlock(args.email, args.reason).email}.")


def run_content(args: argparse.Namespace, store: ContentStore) -> None:
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


def main(
    argv: Sequence[str] | None = None,
    store_factory: StoreFactory = azure_store,
    admin_factory: AdminFactory = azure_user_admin,
) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        if args.group == "content":
            run_content(args, store_factory())
        else:
            run_users(args, admin_factory())
    except (
        BookExistsError,
        BookNotFoundError,
        InvalidPdfError,
        InvalidSlugError,
        ValidationError,
        FileNotFoundError,
        UserAdminError,
        GraphError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
