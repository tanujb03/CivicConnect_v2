"""Request / response shapes of the admin endpoints: user management (A12) and system settings (A13)."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _clean_email(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return None
    v = v.strip().lower()
    if "@" not in v or v.startswith("@") or v.endswith("@") or " " in v:
        raise ValueError("not a valid email address")
    return v


def _clean_phone(v: Optional[str]) -> Optional[str]:
    if v is None or v == "":
        return None
    digits = "".join(ch for ch in v if ch.isdigit() or ch == "+")
    if len(digits.lstrip("+")) < 8:
        raise ValueError("not a valid phone number")
    return digits


# ------------------------------------------------------------------------------------------------ A12 users
class UserAdminOut(BaseModel):
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str                                           # upper case, as everywhere in the API (CITY_ADMIN)
    department_id: Optional[str] = None
    ward_id: Optional[str] = None
    preferred_language: str = "en"
    is_active: bool
    status: str                                         # "active" | "inactive"
    synthetic: bool = False
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None
    cases_reported: int = 0
    must_change_password: bool = False


class UserPage(BaseModel):
    items: list[UserAdminOut]
    next_cursor: Optional[str] = None


class UserCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=32)
    role: str = Field(min_length=1, max_length=32, description="FIELD_WORKER, OPERATOR, DEPARTMENT_MANAGER, WARD_OFFICER, OVERLOOKER, CITY_ADMIN or SYSTEM_ADMIN")
    department_id: Optional[str] = Field(default=None, max_length=64)
    ward_id: Optional[str] = Field(default=None, max_length=36)
    preferred_language: str = Field(default="en", max_length=16)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return _clean_email(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return _clean_phone(v)


class UserCreateOut(BaseModel):
    user: UserAdminOut
    temporary_password: str = Field(description="Shown once; only its hash is stored.")


class PasswordResetOut(BaseModel):
    user: UserAdminOut
    temporary_password: str = Field(description="Shown once; only its hash is stored. The user must change it at the next sign-in.")


class UserPatchIn(BaseModel):
    """Every field is optional; ``department_id`` / ``ward_id`` accept ``null`` to clear them."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    role: Optional[str] = Field(default=None, min_length=1, max_length=32)
    department_id: Optional[str] = Field(default=None, max_length=64)
    ward_id: Optional[str] = Field(default=None, max_length=36)
    is_active: Optional[bool] = None


# ------------------------------------------------------------------------------------------------ A13 settings
class SettingOut(BaseModel):
    key: str
    value: Any
    default: Any
    is_default: bool
    description: str
    updated_by: Optional[str] = None
    updated_at: Optional[datetime] = None


class SettingList(BaseModel):
    items: list[SettingOut]


class SettingsUpdateIn(BaseModel):
    values: dict[str, Any] = Field(min_length=1, description="key -> new value; all values are validated first, one bad value changes nothing")
    reason: Optional[str] = Field(default=None, max_length=500)
