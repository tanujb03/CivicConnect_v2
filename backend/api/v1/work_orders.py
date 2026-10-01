from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from backend.db.session import get_db
from backend.models.case_workflow import WorkOrder
from backend.schemas.work_order import WorkOrderCreate, WorkOrderResponse, WorkOrderListResponse

router = APIRouter()

@router.post("/", response_model=WorkOrderResponse)
def create_work_order(
    work_order: WorkOrderCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    # Idempotency logic would check if key exists in DB/Redis
    db_obj = WorkOrder(**work_order.dict())
    # db.add(db_obj)
    # db.commit()
    # db.refresh(db_obj)
    # Returning mocked object since db is offline
    return {**work_order.dict(), "id": "WO-MOCK-1", "status": "assigned", "created_at": "2026-10-01T00:00:00Z"}

@router.get("/", response_model=WorkOrderListResponse)
def list_work_orders(
    cursor: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    # db.query(WorkOrder).filter(...).limit(limit).all()
    return {"items": [], "next_cursor": None}

@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order(work_order_id: str, db: Session = Depends(get_db)):
    # db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    raise HTTPException(status_code=404, detail="Work order not found")
