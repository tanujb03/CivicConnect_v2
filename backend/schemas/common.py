from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Location(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: Optional[float] = Field(default=None, ge=0)


class Page(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: Optional[str] = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict = {}
    request_id: Optional[str] = None


class ErrorEnvelope(BaseModel):
    error: ErrorBody


Timestamp = datetime
