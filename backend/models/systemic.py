from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from backend.db.session import Base
import uuid

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    content = Column(String, nullable=False)
    entity_id = Column(String, nullable=True) # e.g. case_id or work_order_id
    entity_type = Column(String, nullable=True) 
    is_read = Column(String, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Incident(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True, default=lambda: f"INC-{str(uuid.uuid4())[:8].upper()}")
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    severity = Column(String, default="high")
    status = Column(String, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id = Column(String, ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False) # e.g. "case.status_updated"
    resource_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
