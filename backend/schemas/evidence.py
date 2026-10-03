from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.schemas.common import Location


class UploadInit(BaseModel):
    filename: str = Field(min_length=1, max_length=300)
    mime_type: str = Field(min_length=3, max_length=100)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    source: str = Field(default="SMARTPHONE", max_length=32)
    captured_at: Optional[datetime] = None
    location: Optional[Location] = None
    purpose: Literal["REPORT", "RESOLUTION", "VERIFICATION"] = "REPORT"


class UploadInitOut(BaseModel):
    evidence_id: str
    upload_url: str
    expires_at: datetime
    method: str = "PUT"
    headers: dict[str, str] = {}


class EvidenceOut(BaseModel):
    id: str
    case_id: Optional[str] = None
    media_type: str
    mime_type: str
    size_bytes: int
    status: str
    purpose: str
    filename: Optional[str] = None
    captured_at: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None
    location: Optional[Location] = None
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
