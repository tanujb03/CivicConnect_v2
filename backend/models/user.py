import enum

from sqlalchemy import Boolean, ForeignKey, String, false
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.models.types import JSONType, UTCDateTime, new_id, utcnow


class RoleEnum(str, enum.Enum):
    """Stored lower-case; the API shows the upper-case name (``CITIZEN``) as in design §51A.2."""

    CITIZEN = "citizen"
    FIELD_WORKER = "field_worker"
    OPERATOR = "operator"
    DEPARTMENT_MANAGER = "department_manager"
    WARD_OFFICER = "ward_officer"
    CITY_ADMIN = "city_admin"
    SYSTEM_ADMIN = "system_admin"
    OVERLOOKER = "overlooker"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), unique=True, index=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default=RoleEnum.CITIZEN.value, nullable=False, index=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)   # operators, managers, field workers
    ward_id: Mapped[str | None] = mapped_column(ForeignKey("wards.id"), nullable=True, index=True)               # ward officers
    preferred_language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    accessibility: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)           # seeded demo account
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)
    last_login_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    # migration 0004: staff accounts created or reset by an admin must set their own password before anything else (403 PASSWORD_CHANGE_REQUIRED)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    password_changed_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
