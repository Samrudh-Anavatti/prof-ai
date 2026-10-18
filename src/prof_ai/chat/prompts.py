from pathlib import Path

from prof_ai.profiles.store import ProfileFile, ProfileStore
from prof_ai.users.models import Role, User

BASE_PROMPT = (Path(__file__).parent / "prompts" / "tutor.md").read_text(encoding="utf-8").strip()


def teaching_style_owner(user: User) -> str | None:
    return user.id if user.role == Role.TUTOR else user.tutor_id


def build_system_prompt(user: User, profiles: ProfileStore) -> str:
    """Base prompt, then the tutor's teaching style, then the user's own profile."""
    sections = [BASE_PROMPT]
    style_owner = teaching_style_owner(user)
    style = profiles.get(style_owner, ProfileFile.TEACHING_STYLE) if style_owner else None
    if style:
        sections.append(f"## Your human tutor's teaching style\n\n{style}")
    profile = profiles.get(user.id, ProfileFile.PROFILE)
    if profile:
        sections.append(f"## About the person you're helping\n\n{profile}")
    return "\n\n".join(sections)
