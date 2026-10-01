from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.sql import func
from geoalchemy2 import Geometry
from backend.db.session import Base
import uuid

class CivicCase(Base):
    __tablename__ = "civic_cases"

    id = Column(String, primary_key=True, default=lambda: f"CC-{str(uuid.uuid4())[:8].upper()}")
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String, nullable=False)
    subcategory = Column(String, nullable=True)
    severity = Column(String, default="low")
    status = Column(String, default="reported")
    
    # PostGIS support for geolocation
    location = Column(Geometry('POINT', srid=4326), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    reported_by_id = Column(String, ForeignKey("users.id"), nullable=True)
