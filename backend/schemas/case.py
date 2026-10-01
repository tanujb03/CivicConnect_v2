from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class CivicCaseBase(BaseModel):
    title: str
    description: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    severity: str = "low"

class CivicCaseCreate(CivicCaseBase):
    pass

class CivicCaseResponse(CivicCaseBase):
    id: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class CaseListResponse(BaseModel):
    items: List[CivicCaseResponse]
    next_cursor: Optional[str] = None
