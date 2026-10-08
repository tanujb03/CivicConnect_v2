from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.schemas.auth import ChangePasswordIn, LoginIn, ProfileOut, RefreshIn, RegisterIn, SessionOut, TokenPair
from backend.services import auth as auth_service

router = APIRouter()


class StatusOut(BaseModel):
    status: str = "ok"


@router.post("/register", response_model=SessionOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    """§51A.2 (additive: ``password`` is required because ``/auth/login`` is password based)."""
    user = auth_service.register(db, body)
    out = auth_service.session_for(db, user)
    db.commit()
    return out


@router.post("/login", response_model=SessionOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, body.identifier, body.password)
    out = auth_service.session_for(db, user)
    db.commit()
    return out


@router.post("/token", response_model=SessionOut, include_in_schema=True)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 form login: the 'Authorize' button of the interactive docs (username = email or phone)."""
    user = auth_service.authenticate(db, form.username, form.password)
    out = auth_service.session_for(db, user)
    db.commit()
    return out


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    _, out = auth_service.rotate_refresh(db, body.refresh_token)
    db.commit()
    return {"access_token": out["access_token"], "refresh_token": out["refresh_token"]}


@router.post("/logout", response_model=StatusOut)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    auth_service.revoke_refresh(db, body.refresh_token)
    db.commit()
    return {"status": "ok"}


@router.post("/change-password", response_model=SessionOut)
def change_password(body: ChangePasswordIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Changes the caller's own password, revokes every refresh token and returns a fresh session (user + token pair). Open while ``must_change_password`` is set.
    Deliberately not idempotency-keyed: a replay would have to store the new tokens."""
    try:
        out = auth_service.change_password(db, user, body.current_password, body.new_password)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return out


@router.get("/me", response_model=ProfileOut)
def me(user: User = Depends(current_user)):
    return auth_service.profile(user)
