from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.services import analytics as analytics_service
from backend.services import map as map_service

router = APIRouter()


@router.get("/cases")
def map_cases(bbox: Optional[str] = Query(default=None, description="minLon,minLat,maxLon,maxLat"), category: Optional[str] = None, status: Optional[str] = None,
              priority: Optional[str] = None, from_: Optional[datetime] = Query(default=None, alias="from"), until: Optional[datetime] = None,
              limit: Optional[int] = Query(default=None, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Lightweight markers (§51A.12). Staff: the cases of their scope. Everyone else: privacy-preserving markers (coarse location, no text)."""
    return {"items": map_service.markers(db, user, bbox=bbox, category=category, status=status, priority=priority, from_=from_, until=until, limit=limit)}


@router.get("/hotspots")
def map_hotspots(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Server-computed hotspot geometries with their aggregate metrics (design §39: deterministic grid aggregation)."""
    return {"items": analytics_service.hotspots(db, user)}


@router.get("/recurring-problems")
def map_recurring(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Recurring-problem clusters (design §38); linked case ids are included only for staff."""
    return {"items": analytics_service.recurring_problems(db, user)}
