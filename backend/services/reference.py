"""Reference data for every client (categories, departments, wards). Read-only; the taxonomy is the AI package's, so the apps and the AI never disagree."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Department, Ward
from backend.services.taxonomy import taxonomy

_TAXONOMY_KEYS = ("severities", "priorities", "sla_classes", "departments", "categories")      # copied exactly; reviewer notes / id conventions / aliases stay internal


def taxonomy_payload() -> dict[str, Any]:
    raw = taxonomy().raw
    return {"version": raw["taxonomy_version"], "status": raw.get("status", ""), "supported_languages": list(raw["supported_languages"]), **{k: raw[k] for k in _TAXONOMY_KEYS}}


def departments_payload(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(select(Department).order_by(Department.id)).scalars()
    return [{"id": d.id, "code": d.code, "name": d.name, "description": d.description, "name_i18n": d.name_i18n or {}, "category_coverage": list(d.category_coverage or [])} for d in rows]


def _positions(coords: Any):
    """Every [lon, lat] pair of a GeoJSON coordinates array of any nesting depth (Polygon, MultiPolygon, ...)."""
    if isinstance(coords, (list, tuple)) and coords and isinstance(coords[0], (int, float)):
        yield coords
    elif isinstance(coords, (list, tuple)):
        for c in coords:
            yield from _positions(c)


def bbox(boundary: dict | None) -> list[float] | None:
    if not isinstance(boundary, dict):
        return None
    pts = list(_positions(boundary.get("coordinates")))
    if not pts:
        return None
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    return [round(min(lons), 6), round(min(lats), 6), round(max(lons), 6), round(max(lats), 6)]


def wards_payload(db: Session, include_boundary: bool = False) -> list[dict[str, Any]]:
    out = []
    for w in db.execute(select(Ward).order_by(Ward.label, Ward.id)).scalars():
        item = {"id": w.id, "label": w.label, "name": w.name,
                "centroid": {"latitude": w.centroid_lat, "longitude": w.centroid_lon} if w.centroid_lat is not None and w.centroid_lon is not None else None,
                "bbox": bbox(w.boundary)}
        if include_boundary:
            item["boundary"] = w.boundary
        out.append(item)
    return out
