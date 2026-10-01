from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.core.security import get_current_user, require_roles, oauth2_scheme

router = APIRouter()

@router.get("/")
def get_me(current_user: dict = Depends(get_current_user)):
    """Get the currently authenticated user profile."""
    return {
        "id": current_user["sub"],
        "role": current_user["role"],
        "email": "user@example.com",  # Would be fetched from DB in production
    }

@router.patch("/")
def update_me(
    update_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update the currently authenticated user profile."""
    # In production: db.query(User).filter(User.id == current_user["sub"]).update(update_data)
    return {"status": "updated", "id": current_user["sub"]}

@router.get("/notifications")
def get_my_notifications(
    cursor: str = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the notification feed for the current user."""
    # In production: db.query(Notification).filter(Notification.user_id == current_user["sub"])...
    return {"items": [], "next_cursor": None}

@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    return {"status": "ok", "id": notification_id}
