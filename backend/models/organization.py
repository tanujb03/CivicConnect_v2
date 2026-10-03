from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.session import Base
from backend.models.types import JSONType, UTCDateTime, new_id, utcnow


class Department(Base):
    """``id`` is the taxonomy's department id (e.g. ``road_maintenance``), the same value the AI adapter uses."""

    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    code: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    name_i18n: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    category_coverage: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    municipality_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    boundary: Mapped[dict | None] = mapped_column(JSONType, nullable=True)          # GeoJSON Polygon
    centroid_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    officer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", use_alter=True, name="fk_wards_officer"), nullable=True)
    created_at: Mapped[object] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
