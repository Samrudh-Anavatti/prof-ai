from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    TUTOR = "tutor"
    STUDENT = "student"


class AccountStatus(StrEnum):
    ACTIVE = "active"
    ACCOUNT_LOCKED = "account_locked"


class User(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    email: str
    display_name: str
    role: Role
    status: AccountStatus = AccountStatus.ACTIVE
    tutor_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    action: str
    actor: str
    reason: str = ""
    at: datetime
