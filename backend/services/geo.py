"""Small geometry helpers (portable); PostgreSQL deployments additionally use PostGIS (``cases_near``)."""
from __future__ import annotations

import math
from typing import Iterable

EARTH_RADIUS_M = 6_371_008.8


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def bbox_around(lat: float, lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """(min_lat, min_lon, max_lat, max_lon) that contains the circle (cheap SQL pre-filter)."""
    dlat = math.degrees(radius_m / EARTH_RADIUS_M)
    dlon = math.degrees(radius_m / (EARTH_RADIUS_M * max(math.cos(math.radians(lat)), 1e-6)))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon


def point_in_polygon(lat: float, lon: float, ring: Iterable[Iterable[float]]) -> bool:
    """Ray casting on a GeoJSON ring ([lon, lat] pairs)."""
    pts = [(float(p[0]), float(p[1])) for p in ring]
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def geometry_contains(geometry: dict | None, lat: float, lon: float) -> bool:
    if not geometry:
        return False
    t, c = geometry.get("type"), geometry.get("coordinates")
    if t == "Polygon" and c:
        return point_in_polygon(lat, lon, c[0]) and not any(point_in_polygon(lat, lon, h) for h in c[1:])
    if t == "MultiPolygon" and c:
        return any(point_in_polygon(lat, lon, poly[0]) for poly in c)
    return False


def valid_geometry(geometry: dict | None) -> bool:
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon", "Point"):
        return False
    c = geometry.get("coordinates")
    return bool(c)


def geometry_center(geometry: dict) -> tuple[float, float] | None:
    """(lat, lon) average of the outer ring / the point."""
    t, c = geometry.get("type"), geometry.get("coordinates")
    if t == "Point":
        return float(c[1]), float(c[0])
    ring = c[0] if t == "Polygon" else (c[0][0] if t == "MultiPolygon" else None)
    if not ring:
        return None
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    return sum(float(p[1]) for p in pts) / len(pts), sum(float(p[0]) for p in pts) / len(pts)
