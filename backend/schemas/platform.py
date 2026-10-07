"""Request / response shapes of the tables added by migration 0003 (device tokens, case flags, system settings).

No routes use them yet: the lanes that build the endpoints import these. The allowed values live in ``backend.models`` (FLAG_KINDS, FLAG_STATUSES); a test keeps
the ``Literal`` types below identical to them.
"""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

FlagKind = Literal["STILL_EXISTS", "OUTDATED", "INCORRECT", "INAPPROPRIATE"]
FlagStatus = Literal["OPEN", "UPHELD", "DISMISSED"]
DevicePlatform = Literal["ios", "android", "web"]                       # Expo Platform.OS


class DeviceTokenIn(BaseModel):
    platform: DevicePlatform
    expo_push_token: str = Field(min_length=10, max_length=255, pattern=r"^(Exponent|Expo)PushToken\[.+\]$")
    device_id: Optional[str] = Field(default=None, max_length=128)
    locale: Optional[str] = Field(default=None, max_length=16)


class DeviceTokenOut(BaseModel):
    id: str
    platform: DevicePlatform
    device_id: Optional[str] = None
    locale: Optional[str] = None
    created_at: datetime
    last_seen_at: datetime
    revoked_at: Optional[datetime] = None


class CaseFlagIn(BaseModel):
    kind: FlagKind
    comment: Optional[str] = Field(default=None, max_length=1000)


class CaseFlagOut(BaseModel):
    id: str
    case_id: str
    kind: FlagKind
    comment: Optional[str] = None
    status: FlagStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None


class CaseFlagResolveIn(BaseModel):
    status: Literal["UPHELD", "DISMISSED"]


class SystemSettingIn(BaseModel):
    value: Any = None


class SystemSettingOut(BaseModel):
    key: str
    value: Any = None
    updated_by: Optional[str] = None
    updated_at: datetime
