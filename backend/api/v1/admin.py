"""Administration (CITY_ADMIN, SYSTEM_ADMIN): user management (A12) and system settings (A13). Every change is audited (design §46)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.api.deps import IdempotencyHeader, idempotent
from backend.core.permissions import require_capability
from backend.db.session import get_db
from backend.models import User
from backend.schemas.admin import (
    PasswordResetOut,
    SettingList,
    SettingsUpdateIn,
    UserAdminOut,
    UserCreateIn,
    UserCreateOut,
    UserPage,
    UserPatchIn,
)
from backend.services import admin_users
from backend.services import settings as settings_service

router = APIRouter()
manage_users = require_capability("manage_users")
manage_settings = require_capability("manage_settings")


# ------------------------------------------------------------------------------------------------ A12 users
@router.get("/users", response_model=UserPage)
def list_users(role: Optional[str] = None, department_id: Optional[str] = None, ward_id: Optional[str] = None, is_active: Optional[bool] = None,
               q: Optional[str] = Query(default=None, max_length=100, description="substring of name, email or phone"), cursor: Optional[str] = None,
               limit: Optional[int] = Query(default=None, ge=1), user: User = Depends(manage_users), db: Session = Depends(get_db)):
    items, nxt = admin_users.list_users(db, role=role, department_id=department_id, ward_id=ward_id, is_active=is_active, q=q, cursor=cursor, limit=limit)
    return {"items": items, "next_cursor": nxt}


@router.post("/users", response_model=UserCreateOut, status_code=201)
def create_user(body: UserCreateIn, response: Response, user: User = Depends(manage_users), db: Session = Depends(get_db)):
    """Creates a staff account and returns its generated one-time password ONCE. Deliberately not idempotency-keyed: a replay would have to store the password."""
    try:
        created, password = admin_users.create_user(db, user, body)
        db.commit()
    except Exception:
        db.rollback()
        raise
    response.headers["Cache-Control"] = "no-store"                  # a one-time password must not sit in any cache
    return {"user": admin_users.to_out(created), "temporary_password": password}


@router.post("/users/{user_id}/reset-password", response_model=PasswordResetOut)
def reset_password(user_id: str, response: Response, user: User = Depends(manage_users), db: Session = Depends(get_db)):
    """Sets a new one-time password (returned ONCE), forces a change at the next sign-in and ends the user's sessions. Deliberately not idempotency-keyed
    (like ``POST /admin/users``): a replay would have to store the password."""
    try:
        target, password = admin_users.reset_password(db, user, user_id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    response.headers["Cache-Control"] = "no-store"
    return {"user": admin_users.to_out(target, admin_users.cases_reported(db, target.id)), "temporary_password": password}


@router.patch("/users/{user_id}", response_model=UserAdminOut)
def patch_user(user_id: str, body: UserPatchIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(manage_users),
               db: Session = Depends(get_db)):
    patch = body.model_dump(exclude_unset=True)

    def handler():
        updated = admin_users.update_user(db, user, user_id, patch)
        return 200, UserAdminOut(**admin_users.to_out(updated, admin_users.cases_reported(db, updated.id))).model_dump(mode="json"), updated.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="PATCH", path=f"/admin/users/{user_id}", payload=patch, handler=handler)


# ------------------------------------------------------------------------------------------------ A13 settings
@router.get("/settings", response_model=SettingList)
def get_settings(user: User = Depends(manage_settings), db: Session = Depends(get_db)):
    return {"items": settings_service.list_settings(db)}


@router.put("/settings", response_model=SettingList)
def put_settings(body: SettingsUpdateIn, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(manage_settings),
                 db: Session = Depends(get_db)):
    def handler():
        settings_service.update_settings(db, user, body.values, body.reason)
        db.flush()
        return 200, SettingList(items=settings_service.list_settings(db)).model_dump(mode="json"), None
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="PUT", path="/admin/settings", payload=body.model_dump(mode="json"), handler=handler)
