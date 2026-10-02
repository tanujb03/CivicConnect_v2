from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class WorkOrderBase(BaseModel):
    department_id: str
    assignee_id: Optional[str] = None
    notes: Optional[str] = None

class WorkOrderCreate(WorkOrderBase):
    case_id: str

class WorkOrderResponse(WorkOrderBase):
    id: str
    case_id: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class WorkOrderListResponse(BaseModel):
    items: List[WorkOrderResponse]
    next_cursor: Optional[str] = None
