from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=320)
    phone: Optional[str] = Field(default=None, max_length=32)
    preferred_language: str = Field(default="en", max_length=16)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        if v is None or v == "":
            return None
        v = v.strip().lower()
        if "@" not in v or v.startswith("@") or v.endswith("@") or " " in v:
            raise ValueError("not a valid email address")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        if v is None or v == "":
            return None
        digits = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(digits.lstrip("+")) < 8:
            raise ValueError("not a valid phone number")
        return digits


class LoginIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=300)


class LogoutIn(RefreshIn):
    """Additive: ``expo_push_token`` (same format as ``DeviceTokenIn``) also revokes that device of the refresh token's owner, so a shared phone stops getting their pushes."""

    expo_push_token: Optional[str] = Field(default=None, min_length=10, max_length=255, pattern=r"^(Exponent|Expo)PushToken\[.+\]$")


class ChangePasswordIn(BaseModel):
    """The password policy (length, deny-list, not the current one) is enforced by the service so every refusal has the same envelope (``WEAK_PASSWORD``)."""

    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=1, max_length=200)


class UserBrief(BaseModel):
    id: str
    name: str
    role: str
    must_change_password: bool = False


class SessionOut(BaseModel):
    user: UserBrief
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str


class Accessibility(BaseModel):
    large_text: Optional[bool] = None
    high_contrast: Optional[bool] = None
    reduced_motion: Optional[bool] = None
    voice_playback: Optional[bool] = None


class ProfileOut(BaseModel):
    id: str
    name: str
    role: str
    email: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: str
    accessibility: dict
    department_id: Optional[str] = None
    ward_id: Optional[str] = None
    access_scope: dict
    must_change_password: bool = False


class ProfilePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    preferred_language: Optional[str] = Field(default=None, max_length=16)
    accessibility: Optional[Accessibility] = None
