from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from backend.db.session import Base
import uuid

class ReportSignal(Base):
    __tablename__ = "report_signals"
    id = Column(String, primary_key=True, default=lambda: f"SIG-{str(uuid.uuid4())[:8].upper()}")
    case_id = Column(String, ForeignKey("civic_cases.id"), nullable=True)
    reporter_id = Column(String, ForeignKey("users.id"), nullable=False)
    text_content = Column(Text, nullable=True)
    location = Column(Geometry('POINT', srid=4326), nullable=True)
    status = Column(String, default="pending_fusion") # pending_fusion, fused, standalone
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    id = Column(String, primary_key=True, default=lambda: f"EVI-{str(uuid.uuid4())[:8].upper()}")
    case_id = Column(String, ForeignKey("civic_cases.id"), nullable=True)
    report_id = Column(String, ForeignKey("report_signals.id"), nullable=True)
    work_order_id = Column(String, ForeignKey("work_orders.id"), nullable=True)
    file_url = Column(String, nullable=False)
    media_type = Column(String, nullable=False) # image, video, audio
    uploaded_by_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AIAnalysis(Base):
    __tablename__ = "ai_analyses"
    id = Column(String, primary_key=True, default=lambda: f"AIA-{str(uuid.uuid4())[:8].upper()}")
    case_id = Column(String, ForeignKey("civic_cases.id"), nullable=True)
    report_id = Column(String, ForeignKey("report_signals.id"), nullable=True)
    analysis_type = Column(String, nullable=False) # intake, fusion, triage
    raw_response = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class WorkOrder(Base):
    __tablename__ = "work_orders"
    id = Column(String, primary_key=True, default=lambda: f"WO-{str(uuid.uuid4())[:8].upper()}")
    case_id = Column(String, ForeignKey("civic_cases.id"), nullable=False)
    department_id = Column(String, ForeignKey("departments.id"), nullable=False)
    assignee_id = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="assigned") # assigned, in_progress, resolved
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Verification(Base):
    __tablename__ = "verifications"
    id = Column(String, primary_key=True, default=lambda: f"VER-{str(uuid.uuid4())[:8].upper()}")
    case_id = Column(String, ForeignKey("civic_cases.id"), nullable=False)
    verifier_id = Column(String, ForeignKey("users.id"), nullable=False)
    is_verified = Column(Boolean, nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Support(Base):
    __tablename__ = "supports"
    id = Column(String, primary_key=True, default=lambda: f"SUP-{str(uuid.uuid4())[:8].upper()}")
    case_id = Column(String, ForeignKey("civic_cases.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class CaseRelation(Base):
    __tablename__ = "case_relations"
    id = Column(String, primary_key=True, default=lambda: f"REL-{str(uuid.uuid4())[:8].upper()}")
    primary_case_id = Column(String, ForeignKey("civic_cases.id"), nullable=False)
    secondary_case_id = Column(String, ForeignKey("civic_cases.id"), nullable=False)
    relation_type = Column(String, default="duplicate") # duplicate, related
    confidence = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
