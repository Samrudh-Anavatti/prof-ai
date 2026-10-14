import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

SLUG_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"
SLUG_MAX_LENGTH = 64


class InvalidSlugError(ValueError):
    pass


def validate_slug(slug: str) -> str:
    if len(slug) > SLUG_MAX_LENGTH or not re.fullmatch(SLUG_PATTERN, slug):
        raise InvalidSlugError(
            f"Invalid slug {slug!r}: use lowercase letters, digits and single hyphens "
            f"(max {SLUG_MAX_LENGTH} characters)."
        )
    return slug


class LicenceType(StrEnum):
    OWN = "own"
    LICENSED = "licensed"
    OPEN = "open"
    UNVERIFIED = "unverified"


class Licence(BaseModel):
    type: LicenceType
    notes: str = ""


class Chapter(BaseModel):
    title: str
    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)
    status: Literal["not_extracted"] = "not_extracted"


class BookManifest(BaseModel):
    schema_version: Literal[1] = 1
    slug: str = Field(pattern=SLUG_PATTERN, max_length=SLUG_MAX_LENGTH)
    title: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    grades: list[Annotated[int, Field(ge=1, le=13)]] = Field(min_length=1)
    curriculum: str = ""
    licence: Licence
    source_blob: str
    sha256: str
    page_count: int = Field(ge=1)
    uploaded_at: datetime
    chapters: list[Chapter] = []
