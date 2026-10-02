from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from backend.db.session import Base
import uuid

class Department(Base):
    __tablename__ = "departments"
    id = Column(String, primary_key=True, default=lambda: f"DEPT-{str(uuid.uuid4())[:8].upper()}")
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Ward(Base):
    __tablename__ = "wards"
    id = Column(String, primary_key=True, default=lambda: f"WARD-{str(uuid.uuid4())[:8].upper()}")
    name = Column(String, nullable=False)
    boundary = Column(Geometry('POLYGON', srid=4326), nullable=True)
    officer_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
