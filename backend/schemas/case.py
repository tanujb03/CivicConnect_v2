from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.common import Location

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Priority = Literal["LOW", "NORMAL", "HIGH", "URGENT", "CRITICAL"]


class CaseCreate(BaseModel):
    client_case_id: Optional[str] = Field(default=None, max_length=64)
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=64)
    subcategory: Optional[str] = Field(default=None, max_length=64)
    location: Location
    observed_at: Optional[datetime] = None
    language: str = Field(default="en", max_length=16)
    source: Literal["CITIZEN", "FIELD_WORKER", "ADMIN"] = "CITIZEN"
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class CasePatch(BaseModel):
    """Only the fields the caller's role may change are accepted; anything else is refused with FIELD_NOT_PERMITTED."""

    model_config = ConfigDict(extra="allow")
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = Field(default=None, max_length=5000)
    category: Optional[str] = Field(default=None, max_length=64)
    subcategory: Optional[str] = Field(default=None, max_length=64)
    severity: Optional[Severity] = None
    priority: Optional[Priority] = None
    ward_id: Optional[str] = None
    department_id: Optional[str] = None
    reason: Optional[str] = Field(default=None, max_length=1000)       # required by staff overrides of category / priority (audited)


class CaseOut(BaseModel):
    id: str
    case_number: str
    title: Optional[str] = None
    description: Optional[str] = None
    status: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    severity: Optional[str] = None
    priority: str
    location: Location
    ward_id: Optional[str] = None
    department_id: Optional[str] = None
    support_count: int = 0
    reopen_count: int = 0
    sla_hours: Optional[int] = None
    sla_deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    open_flag_count: int = 0                         # open citizen flags (WP4); staff views only, 0 for everyone else
    needs_flag_review: bool = False                  # open_flag_count >= the flag_review_threshold setting; staff views only
    map_hidden: bool = False                         # hidden from the public map (open INAPPROPRIATE flags at the threshold, or one UPHELD); staff views only


class CaseCreated(BaseModel):
    case: CaseOut


class TimelineItem(BaseModel):
    id: str
    event_type: str
    actor_id: Optional[str] = None
    timestamp: datetime
    metadata: dict[str, Any] = {}


class CaseDetail(CaseOut):
    is_reporter: bool = False
    reporter: Optional[dict] = None                  # staff only (id, name); never shown to other citizens
    contributors: int = 0
    evidence: list[dict] = []
    work_orders: list[dict] = []
    timeline: list[TimelineItem] = []


class ContributorIn(BaseModel):
    user_id: str
    role: Literal["CONTRIBUTOR"] = "CONTRIBUTOR"


class RejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class ReopenIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class VerificationIn(BaseModel):
    result: Literal["YES", "PARTIAL", "STILL_OCCURRING", "NO"]
    comment: Optional[str] = Field(default=None, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)


class VerificationOut(BaseModel):
    id: str
    case_id: str
    result: str
    case_status: str
    reopened: bool
    created_at: datetime
