from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.pagination import clamp_limit, paginate
from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import Notification, User
from backend.schemas.auth import ProfileOut, ProfilePatch
from backend.services import auth as auth_service
from backend.services import notifications as notification_service

router = APIRouter()


class NotificationItem(BaseModel):
    id: str
    type: str
    payload: dict
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    next_cursor: Optional[str] = None


@router.get("", response_model=ProfileOut)
@router.get("/", response_model=ProfileOut, include_in_schema=False)
def get_me(user: User = Depends(current_user)):
    return auth_service.profile(user)


@router.patch("", response_model=ProfileOut)
@router.patch("/", response_model=ProfileOut, include_in_schema=False)
def update_me(body: ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    auth_service.update_profile(db, user, body)
    db.commit()
    return auth_service.profile(user)


@router.get("/notifications", response_model=NotificationPage)
def my_notifications(cursor: Optional[str] = None, limit: Optional[int] = Query(default=None, ge=1), unread: bool = False,
                     user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == user.id)
    if unread:
        q = q.filter(Notification.read_at.is_(None))
    rows, nxt = paginate(q, [(Notification.created_at, True), (Notification.id, True)], cursor, clamp_limit(limit), lambda n: [n.created_at, n.id])
    return {"items": [notification_service.serialize(n) for n in rows], "next_cursor": nxt}


@router.post("/notifications/{notification_id}/read", response_model=NotificationItem)
@router.patch("/notifications/{notification_id}/read", response_model=NotificationItem, include_in_schema=False)
def read_notification(notification_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = notification_service.mark_read(db, user.id, notification_id)
    db.commit()
    return notification_service.serialize(n)
