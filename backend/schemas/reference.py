"""Shapes of the reference-data endpoints (documentation of the response bodies; the routes return pre-serialised JSON with an ETag)."""
from typing import Optional

from pydantic import BaseModel


class SeverityOut(BaseModel):
    id: str
    rank: int
    label: dict[str, str]
    description: Optional[str] = None


class PriorityOut(BaseModel):
    id: str
    rank: int
    default_sla_class: str
    label: dict[str, str]


class SlaClassOut(BaseModel):
    id: str
    hours: int
    label: dict[str, str]


class TaxonomyDepartmentOut(BaseModel):
    id: str
    code: str
    label: dict[str, str]
    category_ids: list[str]


class SubcategoryOut(BaseModel):
    id: str
    label: dict[str, str]
    base_severity: str
    safety_critical: bool
    department_id: Optional[str] = None


class CategoryOut(BaseModel):
    id: str
    label: dict[str, str]
    department_id: str
    subcategories: list[SubcategoryOut]


class TaxonomyOut(BaseModel):
    version: str
    status: str
    supported_languages: list[str]
    severities: list[SeverityOut]
    priorities: list[PriorityOut]
    sla_classes: list[SlaClassOut]
    departments: list[TaxonomyDepartmentOut]
    categories: list[CategoryOut]


class DepartmentRef(BaseModel):
    id: str
    code: Optional[str] = None
    name: str
    description: Optional[str] = None
    name_i18n: dict[str, str] = {}
    category_coverage: list[str] = []


class DepartmentRefList(BaseModel):
    items: list[DepartmentRef]


class Centroid(BaseModel):
    latitude: float
    longitude: float


class WardRef(BaseModel):
    id: str
    label: Optional[str] = None
    name: str
    centroid: Optional[Centroid] = None
    bbox: Optional[list[float]] = None                  # [min_lon, min_lat, max_lon, max_lat]
    boundary: Optional[dict] = None                     # GeoJSON, only with ?include=boundary


class WardRefList(BaseModel):
    items: list[WardRef]
