from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Operation = Literal["CREATE_CASE", "SUPPORT_CASE", "UNSUPPORT_CASE", "ADD_EVIDENCE", "SUBMIT_VERIFICATION", "PATCH_CASE"]


class SyncMutationIn(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    client_timestamp: Optional[datetime] = None
    operation: Operation
    payload: dict[str, Any] = Field(default_factory=dict)


class SyncRequest(BaseModel):
    device_id: Optional[str] = Field(default=None, max_length=64)
    mutations: list[SyncMutationIn] = Field(min_length=1, max_length=50)


class SyncResult(BaseModel):
    idempotency_key: str
    status: Literal["APPLIED", "ALREADY_APPLIED", "REJECTED"]
    server_resource_id: Optional[str] = None
    error: Optional[dict] = None


class SyncResponse(BaseModel):
    results: list[SyncResult]
    server_cursor: str


class SyncChange(BaseModel):
    cursor: str
    case_id: str
    event_type: str
    timestamp: datetime


class SyncChanges(BaseModel):
    changes: list[SyncChange]
    cases: dict[str, dict]
    server_cursor: str
    has_more: bool
