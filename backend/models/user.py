from sqlalchemy import Column, String, DateTime, Enum as SQLEnum, Boolean
from sqlalchemy.sql import func
import enum
import uuid
from backend.db.session import Base

class RoleEnum(str, enum.Enum):
    CITIZEN = "citizen"
    OPERATOR = "operator"
    DEPARTMENT_MANAGER = "department_manager"
    WARD_OFFICER = "ward_officer"
    CITY_ADMIN = "city_admin"
    FIELD_WORKER = "field_worker"
    SYSTEM_ADMIN = "system_admin"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    role = Column(SQLEnum(RoleEnum), default=RoleEnum.CITIZEN, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
