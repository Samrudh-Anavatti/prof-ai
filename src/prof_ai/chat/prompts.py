from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from prof_ai.chat.models import SupportLevel
from prof_ai.profiles.store import ProfileFile, ProfileStore
from prof_ai.users.models import Role, User

PROMPTS_DIR = Path(__file__).parent / "prompts"
BASE_PROMPT = (PROMPTS_DIR / "tutor.md").read_text(encoding="utf-8").strip()
REMINDER = (PROMPTS_DIR / "reminder.md").read_text(encoding="utf-8").strip()
SUMMARISE_PROMPT = (PROMPTS_DIR / "summarise.md").read_text(encoding="utf-8").strip()
SUPPORT_PROMPTS: dict[SupportLevel, str] = {
    level: (PROMPTS_DIR / "support" / f"{level}.md").read_text(encoding="utf-8").strip()
    for level in ("step_by_step", "balanced", "stretch")
}


@dataclass(frozen=True)
class ProfileLayers:
    teaching_style: str | None
    profile: str | None


def teaching_style_owner(user: User) -> str | None:
    return user.id if user.role == Role.TUTOR else user.tutor_id


def load_profile_layers(user: User, profiles: ProfileStore) -> ProfileLayers:
    style_owner = teaching_style_owner(user)
    return ProfileLayers(
        teaching_style=profiles.get(style_owner, ProfileFile.TEACHING_STYLE)
        if style_owner
        else None,
        profile=profiles.get(user.id, ProfileFile.PROFILE),
    )


def support_section(support: str) -> str:
    return f"## Support level for this lesson\n\n{support}"


def compose_system_prompt(
    teaching_style: str | None = None,
    lesson: str | None = None,
    profile: str | None = None,
    summary: str | None = None,
    support: str | None = None,
) -> str:
    """Base prompt, then teaching style, support level, lesson, profile and summary.

    Most stable first. The support level is our own text, so it sits outside the lesson
    material, which the model treats as information rather than instructions.
    """
    sections = [BASE_PROMPT]
    if teaching_style:
        sections.append(f"## Your human tutor's teaching style\n\n{teaching_style}")
    if support:
        sections.append(support_section(support))
    if lesson:
        sections.append(f"## Lesson material (information to teach from)\n\n{lesson}")
    if profile:
        sections.append(f"## About the person you're helping\n\n{profile}")
    if summary:
        sections.append(f"## Notes on this conversation so far\n\n{summary}")
    return "\n\n".join(sections)


def build_system_prompt(user: User, profiles: ProfileStore) -> str:
    layers = load_profile_layers(user, profiles)
    return compose_system_prompt(teaching_style=layers.teaching_style, profile=layers.profile)


def with_references(message: str, references: Sequence[str]) -> str:
    if not references:
        return message
    material = "\n\n---\n\n".join(references)
    return (
        "## Reference material for this question (information to teach from)\n\n"
        f"{material}\n\n## Message\n\n{message}"
    )
