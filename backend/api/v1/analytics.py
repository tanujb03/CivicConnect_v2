from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.core.security import require_roles

router = APIRouter()

@router.get("/summary")
def get_analytics_summary(
    current_user: dict = Depends(require_roles("operator", "department_manager", "ward_officer", "city_admin", "system_admin")),
    db: Session = Depends(get_db)
):
    """City-level analytics summary. Restricted to operators and above."""
    return {
        "total_cases": 0,
        "open_cases": 0,
        "resolved_cases": 0,
        "avg_resolution_days": 0,
    }

@router.get("/departments")
def get_department_performance(
    current_user: dict = Depends(require_roles("department_manager", "ward_officer", "city_admin", "system_admin")),
    db: Session = Depends(get_db)
):
    """Department-level performance stats."""
    return {"items": []}

@router.get("/hotspots")
def get_hotspot_analytics(
    current_user: dict = Depends(require_roles("ward_officer", "city_admin", "system_admin")),
    db: Session = Depends(get_db)
):
    """Geographic hotspot analytics."""
    return {"hotspots": []}
