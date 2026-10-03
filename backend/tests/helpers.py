"""Shared helpers for the API tests."""
from __future__ import annotations

import hashlib

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"civicconnect-test-image-bytes" * 8
WAV = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"fmt " + b"\x00" * 20


def upload(e, who: str, data: bytes = JPEG, mime: str = "image/jpeg", name: str = "photo.jpg", purpose: str = "REPORT", complete: bool = True) -> dict:
    """The full §51A.6 protocol through the API: init -> PUT to the signed URL -> complete. Returns the final evidence metadata (or the init response)."""
    from backend.core.config import settings
    sha = hashlib.sha256(data).hexdigest()
    init = e.client.post("/api/v1/evidence/upload-init", headers=e.idem(who),
                         json={"filename": name, "mime_type": mime, "size_bytes": len(data), "sha256": sha, "purpose": purpose, "source": "SMARTPHONE"})
    assert init.status_code == 201, init.text
    body = init.json()
    path = body["upload_url"].replace(settings.PUBLIC_BASE_URL.rstrip("/"), "")
    put = e.client.put(path, content=data, headers={"Content-Type": mime})
    assert put.status_code == 204, put.text
    if not complete:
        return body
    done = e.client.post(f"/api/v1/evidence/{body['evidence_id']}/complete", headers=e.headers(who))
    assert done.status_code == 200, done.text
    return done.json()


def case_body(e, **kw) -> dict:
    return {"description": "Huge pothole outside the school gate, two bikes already fell", "category": "roads", "subcategory": "pothole", "location": e.where, "language": "en", **kw}


def create_case(e, who: str = "alice", **kw) -> dict:
    r = e.client.post("/api/v1/cases", headers=e.idem(who), json=case_body(e, **kw))
    assert r.status_code in (200, 201), r.text
    return r.json()["case"]
