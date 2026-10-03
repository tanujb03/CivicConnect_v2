from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class IncidentCreate(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    description: str = Field(default="", max_length=5000)
    category: Optional[str] = Field(default=None, max_length=64)
    boundary: dict[str, Any]
    case_ids: list[str] = Field(default_factory=list, max_length=500)


class IncidentPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=3, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None, pattern="^(ACTIVE|ENDED)$")


class IncidentAddCase(BaseModel):
    case_id: str


class IncidentOut(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    status: str
    boundary: Optional[dict] = None
    ward_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    case_count: int = 0


class IncidentDetail(IncidentOut):
    case_ids: list[str] = []
    departments: list[str] = []
    work_orders: list[dict] = []
    timeline: list[dict] = []
