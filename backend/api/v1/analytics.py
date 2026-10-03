from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.ai_gateway import AIGateway, get_actor, get_gateway
from backend.ai_gateway.contracts import AnalyticsExplainRequest, AnalyticsExplainResponse
from backend.ai_gateway.service import Actor
from backend.core.permissions import require_capability
from backend.db.session import get_db
from backend.models import User
from backend.schemas.analytics import DepartmentStatsList, DepartmentStatsOut, TrendsOut, WardStatsList
from backend.services import analytics as analytics_service

router = APIRouter()
view = require_capability("view_analytics")


@router.get("/overview")
def analytics_overview(days: int = Query(default=30, ge=7, le=365), user: User = Depends(view), db: Session = Depends(get_db)):
    """§51A.13 aggregate operational metrics for the caller's scope (staff: their scope; overlooker: whole city, aggregates only)."""
    return analytics_service.overview(db, user, days=days)


@router.get("/trends", response_model=TrendsOut)
def analytics_trends(granularity: Literal["daily", "weekly"] = "daily", days: int = Query(default=30, ge=7, le=365), category: Optional[str] = Query(default=None, max_length=64),
                     user: User = Depends(view), db: Session = Depends(get_db)):
    """Cases created per day or ISO week (Monday, UTC) by category and status, plus created / resolved / critical totals per bucket. Grouped in SQL, scoped to the caller's role."""
    return analytics_service.trends(db, user, granularity=granularity, days=days, category=category)


@router.get("/departments/{department_id}", response_model=DepartmentStatsOut)
def analytics_department(department_id: str, days: int = Query(default=30, ge=7, le=365), user: User = Depends(view), db: Session = Depends(get_db)):
    """A07: incoming and resolved over the last ``days`` days, median resolution, SLA compliance, open workload by severity, backlog age, reopened, recurring cases."""
    return analytics_service.department(db, user, department_id, days=days)


@router.get("/departments", response_model=DepartmentStatsList)
def analytics_departments(days: int = Query(default=30, ge=7, le=365), user: User = Depends(view), db: Session = Depends(get_db)):
    return {"items": analytics_service.departments(db, user, days=days)}


@router.get("/wards", response_model=WardStatsList)
def analytics_wards(days: Optional[int] = Query(default=None, ge=1, le=3650, description="only cases created in the last N days (default: all time)"),
                    user: User = Depends(view), db: Session = Depends(get_db)):
    """A09: per ward cases, open, critical, backlog, median resolution days, recurring sites and the category distribution."""
    return {"items": analytics_service.wards(db, user, days=days)}


@router.get("/hotspots")
def analytics_hotspots(user: User = Depends(view), db: Session = Depends(get_db)):
    return {"items": analytics_service.hotspots(db, user)}


@router.get("/recurrence")
def analytics_recurrence(user: User = Depends(view), db: Session = Depends(get_db)):
    return {"items": analytics_service.recurring_problems(db, user)}


@router.get("/incidents")
def analytics_incidents(cursor: Optional[str] = None, limit: Optional[int] = Query(default=None, ge=1), user: User = Depends(view), db: Session = Depends(get_db)):
    items, nxt = analytics_service.incidents_summary(db, user, cursor=cursor, limit=limit)
    return {"items": items, "next_cursor": nxt}


@router.post("/explain", response_model=AnalyticsExplainResponse)
def explain_analytics(request: AnalyticsExplainRequest, actor: Actor = Depends(get_actor), gateway: AIGateway = Depends(get_gateway)):
    """AI-5 (additive, not in §51A): plain-language explanation of deterministic analytics facts. Numbers come from ``facts``; the prose is verified against them."""
    return gateway.explain_analytics(request, actor)
