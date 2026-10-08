from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.models.types import JSONType, UTCDateTime, new_id, utcnow


class RefreshToken(Base):
    """Rotating refresh tokens: only a hash is stored; using a token revokes it and issues the next one."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[object] = mapped_column(UTCDateTime, nullable=False)
    revoked_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class IdempotencyKey(Base):
    """§51A.1: a retried mutation with the same key replays the stored response; the same key with another body is refused."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_idem_user_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[str] = mapped_column(String(8), nullable=False)
    path: Mapped[str] = mapped_column(String(300), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_json: Mapped[dict | list | None] = mapped_column(JSONType, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class SystemSetting(Base):
    """Runtime-editable settings (key -> JSON value), e.g. feature switches; ``updated_by`` is the admin who last changed it."""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value_json: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONType, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DeviceToken(Base):
    """An Expo push token of one installed app instance of a user (citizen and field-worker apps are Expo). Revoked tokens are kept, never reused."""

    __tablename__ = "device_tokens"
    __table_args__ = (Index("ix_device_tokens_user_active", "user_id", "revoked_at"),)      # "the active tokens of a user" (push sender, device list)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)                      # Expo Platform.OS: "ios" | "android" | "web"
    expo_push_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    last_seen_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    revoked_at: Mapped[object | None] = mapped_column(UTCDateTime, nullable=True)
