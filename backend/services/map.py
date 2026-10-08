"""Lightweight map markers (§51A.12). Staff see the cases of their scope; citizens, field workers and the overlooker get privacy-preserving markers of the whole city."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from backend.core.exceptions import CivicConnectException
from backend.core.permissions import STAFF_ROLES
from backend.models import CivicCase, User
from backend.services import flags as flag_service
from backend.services.cases import visibility_clause


def parse_bbox(bbox: str | None) -> tuple[float, float, float, float] | None:
    """``minLon,minLat,maxLon,maxLat`` -> (min_lat, min_lon, max_lat, max_lon)."""
    if not bbox:
        return None
    try:
        a = [float(x) for x in bbox.split(",")]
        if len(a) != 4 or not (-180 <= a[0] < a[2] <= 180 and -90 <= a[1] < a[3] <= 90):
            raise ValueError
    except ValueError:
        raise CivicConnectException("VALIDATION_ERROR", "bbox must be minLon,minLat,maxLon,maxLat within valid ranges.", 422, {"field": "bbox"})
    return a[1], a[0], a[3], a[2]


def markers(db: Session, user: User, *, bbox: str | None, category: str | None, status: str | None, priority: str | None, from_: datetime | None, until: datetime | None,
            limit: int | None) -> list[dict]:
    q = db.query(CivicCase)
    if user.role in STAFF_ROLES:
        clause = visibility_clause(user)
        if clause is not True:
            q = q.filter(clause)
    else:
        q = q.filter(CivicCase.status != "REJECTED", CivicCase.id.not_in(flag_service.hidden_from_public_map(db)))      # reported as inappropriate until staff resolve the flags
    box = parse_bbox(bbox)
    if box:
        q = q.filter(CivicCase.latitude.between(box[0], box[2]), CivicCase.longitude.between(box[1], box[3]))
    if category:
        q = q.filter(CivicCase.category == category)
    if status:
        q = q.filter(CivicCase.status.in_([s.strip().upper() for s in status.split(",") if s.strip()]))
    if priority:
        q = q.filter(CivicCase.priority.in_([p.strip().upper() for p in priority.split(",") if p.strip()]))
    if from_:
        q = q.filter(CivicCase.created_at >= from_)
    if until:
        q = q.filter(CivicCase.created_at <= until)
    n = max(1, min(limit or 500, 2000))
    rows = q.order_by(CivicCase.created_at.desc(), CivicCase.id).limit(n).all()
    staff = user.role in STAFF_ROLES
    return [{"id": c.id, "case_number": c.case_number, "location": {"latitude": c.latitude, "longitude": c.longitude} if staff else {"latitude": round(c.latitude, 4), "longitude": round(c.longitude, 4)},
             "status": c.status, "category": c.category, "priority": c.priority, "support_count": c.support_count} for c in rows]
