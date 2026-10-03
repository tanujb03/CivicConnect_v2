from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkOrderCreate(BaseModel):
    assignee_id: str
    instructions: str = Field(min_length=1, max_length=4000)
    due_at: Optional[datetime] = None


class WorkOrderCreateLegacy(WorkOrderCreate):
    case_id: str


class WorkOrderComplete(BaseModel):
    notes: str = Field(default="", max_length=4000)
    resolution_evidence_ids: list[str] = Field(default_factory=list, max_length=10)


class WorkOrderPatch(BaseModel):
    assignee_id: Optional[str] = None
    instructions: Optional[str] = Field(default=None, max_length=4000)
    due_at: Optional[datetime] = None
    priority: Optional[str] = None


class WorkOrderOut(BaseModel):
    id: str
    case_id: str
    case_number: Optional[str] = None
    department_id: Optional[str] = None
    assignee_id: Optional[str] = None
    priority: str
    due_at: Optional[datetime] = None
    instructions: Optional[str] = None
    notes: Optional[str] = None
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class WorkOrderDetail(WorkOrderOut):
    case: dict = {}
    evidence: list[dict] = []
    resolution_review: Optional[dict] = None          # AI-4 flags (staff only; flag-only, never changes state)
