from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.core.security import get_current_user, require_roles
from backend.models.systemic import Incident, AuditEvent

router = APIRouter()

@router.get("/")
def list_incidents(
    cursor: str = None,
    limit: int = 20,
    current_user: dict = Depends(require_roles("ward_officer", "city_admin", "system_admin")),
    db: Session = Depends(get_db)
):
    """List incidents. Restricted to ward officer and above."""
    return {"items": [], "next_cursor": None}

@router.post("/")
def create_incident(
    incident_data: dict,
    current_user: dict = Depends(require_roles("ward_officer", "city_admin", "system_admin")),
    db: Session = Depends(get_db)
):
    """Create a new incident. Restricted to ward officer and above."""
    return {"id": "INC-MOCK-1", "status": "active", **incident_data}

@router.get("/{incident_id}")
def get_incident(
    incident_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    raise HTTPException(status_code=404, detail="Incident not found")
