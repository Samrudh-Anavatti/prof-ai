import argparse
import base64
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from prof_ai.chat.models import TurnContext
from prof_ai.chat.prompts import build_system_prompt
from prof_ai.chat.store import ChatStore
from prof_ai.content.manifest import InvalidSlugError, Licence, LicenceType
from prof_ai.content.pdf import InvalidPdfError
from prof_ai.content.store import BookExistsError, BookNotFoundError, ContentStore
from prof_ai.graph import GraphError
from prof_ai.profiles.store import InvalidProfileError, ProfileFile, ProfileStore
from prof_ai.users.admin import SIGN_UP_INSTRUCTIONS, UserAdmin, UserAdminError
from prof_ai.users.models import Role, User
from prof_ai.users.repository import UserRepository


class NotFoundError(Exception):
    pass


@dataclass(frozen=True)
class TutorTools:
    users: UserRepository
    profiles: ProfileStore
    chats: ChatStore

    def user(self, email: str) -> User:
        user = self.users.find_by_email(email.strip().lower())
        if user is None:
            raise NotFoundError(f"No account for {email}.")
        return user


StoreFactory = Callable[[], ContentStore]
AdminFactory = Callable[[], UserAdmin]
ToolsFactory = Callable[[], TutorTools]


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
    from prof_ai.users.directory import ExternalIdDirectory

    tools = azure_tutor_tools()
    directory = ExternalIdDirectory(
        GraphClient(AzureCliCredential(tenant_id=require_env("EXTERNAL_TENANT_ID")))
    )

    def erase_user_data(user_id: str) -> None:
        tools.chats.delete_user_data(user_id)
        tools.profiles.delete_all(user_id)

    return UserAdmin(tools.users, directory, signed_in_actor(AzureCliCredential()), erase_user_data)


def azure_tutor_tools() -> TutorTools:
    from azure.identity import AzureCliCredential

    from prof_ai.chat.cosmos_store import CosmosChatStore
    from prof_ai.content.azure_backend import AzureBlobBackend
    from prof_ai.users.cosmos_repository import CosmosUserRepository

    credential = AzureCliCredential()
    cosmos_endpoint = require_env("COSMOS_ENDPOINT")
    return TutorTools(
        CosmosUserRepository(cosmos_endpoint, credential),
        ProfileStore(AzureBlobBackend(require_env("STORAGE_ACCOUNT_URL"), credential)),
        CosmosChatStore(cosmos_endpoint, credential),
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

    remove = user_commands.add_parser(
        "remove", help="Delete an account with its chats, usage and profile files."
    )
    remove.add_argument("email")

    set_admin = user_commands.add_parser(
        "set-admin", help="Let a tutor manage every account in the web app."
    )
    set_admin.add_argument("email")
    set_admin.add_argument("--revoke", action="store_true")

    profiles = groups.add_parser("profiles", help="What the AI is told about each user.")
    profile_commands = profiles.add_subparsers(dest="command", required=True)

    show_profile = profile_commands.add_parser(
        "show", help="Print a user's profile files and the full system prompt."
    )
    show_profile.add_argument("email")

    set_profile = profile_commands.add_parser("set", help="Upload a user's profile files.")
    set_profile.add_argument("email")
    set_profile.add_argument("--profile", type=Path, help="Markdown about this user.")
    set_profile.add_argument(
        "--teaching-style", type=Path, help="Tutors only: applies to them and their students."
    )

    chats = groups.add_parser("chats", help="Read chat transcripts.")
    chat_commands = chats.add_subparsers(dest="command", required=True)
    list_chats = chat_commands.add_parser("list", help="List a user's chats.")
    list_chats.add_argument("email")
    show_chat = chat_commands.add_parser("show", help="Print a chat transcript.")
    show_chat.add_argument("email")
    show_chat.add_argument("conversation_id")
    return parser


def run_users(args: argparse.Namespace, admin: UserAdmin) -> None:
    if args.command == "add":
        user = admin.add(args.email, args.name, Role(args.role), args.tutor)
        print(f"Invited {user.role} {user.email}. {SIGN_UP_INSTRUCTIONS}")
    elif args.command == "list":
        for user in admin.list():
            admin_flag = "admin" if user.is_admin else "-"
            print(
                f"{user.email}\t{user.display_name}\t{user.role}\t{user.status}\t"
                f"{admin_flag}\t{user.id}"
            )
    elif args.command == "lock":
        print(f"Locked {admin.lock(args.email, args.reason).email}.")
    elif args.command == "unlock":
        print(f"Unlocked {admin.unlock(args.email, args.reason).email}.")
    elif args.command == "remove":
        print(f"Removed {admin.remove(args.email).email} and their data.")
    elif args.command == "set-admin":
        user = admin.set_admin(args.email, not args.revoke)
        print(f"{user.email} is {'now' if user.is_admin else 'no longer'} an admin.")


def run_profiles(args: argparse.Namespace, tools: TutorTools) -> None:
    user = tools.user(args.email)
    if args.command == "show":
        for file in ProfileFile:
            text = tools.profiles.get(user.id, file)
            print(f"--- {file} ---\n{text or '(none)'}\n")
        print(f"--- system prompt ---\n{build_system_prompt(user, tools.profiles)}")
    elif args.command == "set":
        if not (args.profile or args.teaching_style):
            raise InvalidProfileError("Pass --profile and/or --teaching-style.")
        if args.teaching_style and user.role != Role.TUTOR:
            raise InvalidProfileError("Only tutors have a teaching style.")
        if args.profile:
            tools.profiles.put(user.id, ProfileFile.PROFILE, args.profile.read_text("utf-8"))
            print(f"Updated {ProfileFile.PROFILE} for {user.email}.")
        if args.teaching_style:
            text = args.teaching_style.read_text("utf-8")
            tools.profiles.put(user.id, ProfileFile.TEACHING_STYLE, text)
            print(f"Updated {ProfileFile.TEACHING_STYLE} for {user.email}.")


def context_sizes(context: TurnContext) -> str:
    layers = ", ".join(f"{name} {size}" for name, size in context.layers.items() if size)
    return (
        f"estimated {context.estimated_input} ({layers}); "
        f"reported {context.input_tokens} in ({context.cached_input_tokens} cached), "
        f"{context.output_tokens} out, ${context.cost_micro_usd / 1_000_000:.4f}"
    )


def run_chats(args: argparse.Namespace, tools: TutorTools) -> None:
    user = tools.user(args.email)
    if args.command == "list":
        for chat in tools.chats.list_conversations(user.id):
            print(
                f"{chat.id}\t{chat.updated_at:%Y-%m-%d %H:%M}\t{len(chat.messages)} messages\t"
                f"{chat.input_tokens + chat.output_tokens} tokens\t{len(chat.flags)} flags\t"
                f"{chat.title or '(untitled)'}"
            )
    elif args.command == "show":
        chat = tools.chats.get_conversation(user.id, args.conversation_id)
        if chat is None:
            raise NotFoundError(f"No chat {args.conversation_id} for {user.email}.")
        if chat.summary:
            print(f"--- summary of the first {chat.summarised_count} messages ---")
            print(f"{chat.summary}\n")
        for message in chat.messages:
            print(f"[{message.at:%Y-%m-%d %H:%M}] {message.role}:\n{message.content}\n")
            if message.context:
                print(f"  context: {context_sizes(message.context)}\n")
        for flag in chat.flags:
            print(f"FLAG [{flag.at:%Y-%m-%d %H:%M}] {flag.kind}: {flag.message}")


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
    tools_factory: ToolsFactory = azure_tutor_tools,
) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        if args.group == "content":
            run_content(args, store_factory())
        elif args.group == "users":
            run_users(args, admin_factory())
        elif args.group == "profiles":
            run_profiles(args, tools_factory())
        else:
            run_chats(args, tools_factory())
    except (
        BookExistsError,
        BookNotFoundError,
        InvalidPdfError,
        InvalidSlugError,
        ValidationError,
        FileNotFoundError,
        UserAdminError,
        GraphError,
        InvalidProfileError,
        NotFoundError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
