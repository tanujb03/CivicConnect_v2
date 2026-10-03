"""Conditional GET for rarely-changing reference data: a strong ETag (content hash) and ``Cache-Control``; ``If-None-Match`` gets ``304`` with an empty body."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import Request, Response


def _etag_matches(header: str | None, etag: str) -> bool:
    if not header:
        return False
    if header.strip() == "*":
        return True
    return any(candidate.strip().removeprefix("W/") == etag for candidate in header.split(","))


def cached_json(request: Request, payload: Any, *, max_age: int = 300) -> Response:
    """``payload`` must be deterministic for unchanged data (stable ordering). ``private``: the endpoints need a login, shared caches must not keep them."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    headers = {"ETag": etag, "Cache-Control": f"private, max-age={max_age}"}
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)
