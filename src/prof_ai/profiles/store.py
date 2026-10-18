from enum import StrEnum

from prof_ai.content.store import BlobBackend

PROFILES_CONTAINER = "profiles"
MAX_PROFILE_BYTES = 8 * 1024


class ProfileFile(StrEnum):
    PROFILE = "profile.md"
    TEACHING_STYLE = "teaching-style.md"


class InvalidProfileError(Exception):
    pass


def profile_path(user_id: str, file: ProfileFile) -> str:
    return f"{user_id}/{file}"


class ProfileStore:
    """Per-user markdown that tutors write and the chat injects into the system prompt."""

    def __init__(self, backend: BlobBackend):
        self._backend = backend

    def get(self, user_id: str, file: ProfileFile) -> str | None:
        path = profile_path(user_id, file)
        if not self._backend.exists(PROFILES_CONTAINER, path):
            return None
        data = self._backend.download(PROFILES_CONTAINER, path)[:MAX_PROFILE_BYTES]
        return data.decode("utf-8", errors="ignore").strip() or None

    def put(self, user_id: str, file: ProfileFile, text: str) -> None:
        data = text.strip().encode("utf-8")
        if not data:
            raise InvalidProfileError("The profile is empty.")
        if len(data) > MAX_PROFILE_BYTES:
            raise InvalidProfileError(
                f"The profile is {len(data)} bytes; the limit is {MAX_PROFILE_BYTES}."
            )
        self._backend.upload(
            PROFILES_CONTAINER, profile_path(user_id, file), data, "text/markdown; charset=utf-8"
        )
