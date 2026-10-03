"""Opaque keyset cursors (§51A.1): ``{"items": [...], "next_cursor": "..." | null}``."""
from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query

from backend.core.exceptions import CivicConnectException

MAX_LIMIT = 100
DEFAULT_LIMIT = 25


def clamp_limit(limit: int | None, default: int = DEFAULT_LIMIT) -> int:
    if limit is None:
        return default
    if limit < 1:
        raise CivicConnectException("VALIDATION_ERROR", "limit must be at least 1.", 422, {"field": "limit"})
    return min(limit, MAX_LIMIT)


def _enc(v: Any) -> Any:
    return {"$dt": v.isoformat()} if isinstance(v, datetime) else v


def _dec(v: Any) -> Any:
    return datetime.fromisoformat(v["$dt"]) if isinstance(v, dict) and "$dt" in v else v


def encode_cursor(values: Sequence[Any]) -> str:
    return base64.urlsafe_b64encode(json.dumps([_enc(v) for v in values], separators=(",", ":")).encode()).decode().rstrip("=")


def decode_cursor(cursor: str, width: int) -> list[Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        vals = [_dec(v) for v in json.loads(raw)]
        if not isinstance(vals, list) or len(vals) != width:
            raise ValueError("shape")
        return vals
    except Exception:
        raise CivicConnectException("INVALID_CURSOR", "The pagination cursor is not valid.", 422)


def paginate(query: Query, order: Sequence[tuple[Any, bool]], cursor: str | None, limit: int, row_values) -> tuple[list, str | None]:
    """``order`` = [(column, descending)], the last one must be unique (the id). ``row_values(row)`` returns the sort-key values of a row, in the same order.
    Returns (rows, next_cursor)."""
    if cursor:
        vals = decode_cursor(cursor, len(order))
        clauses = []
        for i in range(len(order)):
            eq = [order[j][0] == vals[j] for j in range(i)]
            col, desc = order[i]
            clauses.append(and_(*eq, (col < vals[i]) if desc else (col > vals[i])))
        query = query.filter(or_(*clauses))
    query = query.order_by(*[(c.desc() if d else c.asc()) for c, d in order])
    rows = query.limit(limit + 1).all()
    nxt = None
    if len(rows) > limit:
        rows = rows[:limit]
        nxt = encode_cursor(row_values(rows[-1]))
    return rows, nxt
