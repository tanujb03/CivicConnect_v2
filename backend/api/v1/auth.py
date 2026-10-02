from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from backend.db.session import get_db
from backend.core.security import create_access_token, verify_password
from backend.core.config import settings
from backend.models.user import User

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

@router.post("/login")
def login_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    # Mocking user verification since we don't have a real DB populated yet
    if form_data.username == "admin" and form_data.password == "admin":
        user_id = "mock-admin-id"
        role = "system_admin"
    elif form_data.username == "citizen" and form_data.password == "citizen":
        user_id = "mock-citizen-id"
        role = "citizen"
    else:
        # In a real app, we query the DB
        # user = db.query(User).filter(User.email == form_data.username).first()
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            subject=user_id, role=role, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
