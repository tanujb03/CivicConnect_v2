"""Evidence metadata + the upload protocol of §51A.6 (init -> client PUT -> complete), with the checks design §44 asks for."""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.models import CivicCase, EvidenceItem, User
from backend.schemas.evidence import UploadInit
from backend.services.workflow import add_event
from backend.storage import get_storage

log = logging.getLogger("civicconnect.evidence")

# mime -> (media_type, allowed extensions)
ALLOWED: dict[str, tuple[str, frozenset[str]]] = {
    "image/jpeg": ("IMAGE", frozenset({".jpg", ".jpeg"})), "image/png": ("IMAGE", frozenset({".png"})), "image/webp": ("IMAGE", frozenset({".webp"})),
    "image/heic": ("IMAGE", frozenset({".heic"})), "image/heif": ("IMAGE", frozenset({".heif", ".heic"})),
    "audio/webm": ("AUDIO", frozenset({".webm"})), "audio/ogg": ("AUDIO", frozenset({".ogg", ".opus"})), "audio/wav": ("AUDIO", frozenset({".wav"})),
    "audio/x-wav": ("AUDIO", frozenset({".wav"})), "audio/mpeg": ("AUDIO", frozenset({".mp3"})), "audio/mp4": ("AUDIO", frozenset({".m4a", ".mp4"})),
    "audio/x-m4a": ("AUDIO", frozenset({".m4a"})), "audio/aac": ("AUDIO", frozenset({".aac"})),
    "video/mp4": ("VIDEO", frozenset({".mp4"})), "video/webm": ("VIDEO", frozenset({".webm"})), "video/quicktime": ("VIDEO", frozenset({".mov"})),
}


def media_type_of(mime: str) -> str:
    return ALLOWED[mime][0]


def sniff_ok(mime: str, head: bytes) -> bool:
    """Content inspection (design §44): the first bytes must look like what the client claims."""
    if mime == "image/jpeg":
        return head[:3] == b"\xff\xd8\xff"
    if mime == "image/png":
        return head[:8] == b"\x89PNG\r\n\x1a\n"
    if mime == "image/webp":
        return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if mime in ("image/heic", "image/heif", "audio/mp4", "audio/x-m4a", "video/mp4", "video/quicktime"):
        return head[4:8] == b"ftyp"
    if mime in ("audio/webm", "video/webm"):
        return head[:4] == b"\x1a\x45\xdf\xa3"
    if mime == "audio/ogg":
        return head[:4] == b"OggS"
    if mime in ("audio/wav", "audio/x-wav"):
        return head[:4] == b"RIFF" and head[8:12] == b"WAVE"
    if mime == "audio/mpeg":
        return head[:3] == b"ID3" or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0)
    if mime == "audio/aac":
        return len(head) > 1 and head[0] == 0xFF and head[1] & 0xF0 == 0xF0
    return False


def _ext(filename: str) -> str:
    i = filename.rfind(".")
    return filename[i:].lower() if i >= 0 else ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def init_upload(db: Session, user: User, body: UploadInit) -> tuple[EvidenceItem, str, datetime]:
    mime = body.mime_type.lower().split(";")[0].strip()
    if mime not in ALLOWED:
        raise CivicConnectException("UNSUPPORTED_MEDIA_TYPE", "That file type is not accepted.", 415, {"mime_type": body.mime_type, "allowed": sorted(ALLOWED)})
    if _ext(body.filename) not in ALLOWED[mime][1]:
        raise CivicConnectException("UNSUPPORTED_MEDIA_TYPE", "The file extension does not match its type.", 415, {"filename": body.filename})
    if body.size_bytes > settings.MAX_UPLOAD_BYTES:
        raise CivicConnectException("PAYLOAD_TOO_LARGE", "The file is larger than the allowed size.", 413, {"max_bytes": settings.MAX_UPLOAD_BYTES})
    now = _now()
    key = f"evidence/{now:%Y/%m}/{uuid.uuid4().hex}{_ext(body.filename)}"        # generated, never derived from user input
    ev = EvidenceItem(uploader_id=user.id, purpose=body.purpose, object_key=key, filename=body.filename[:300], media_type=media_type_of(mime), mime_type=mime,
                      size_bytes=body.size_bytes, sha256=body.sha256.lower(), status="PENDING", source=body.source, captured_at=body.captured_at,
                      latitude=body.location.latitude if body.location else None, longitude=body.location.longitude if body.location else None)
    db.add(ev)
    db.flush()
    ttl = settings.SIGNED_URL_TTL_SECONDS
    return ev, get_storage().upload_url(key, mime, ttl), now + timedelta(seconds=ttl)


def complete_upload(db: Session, user: User, evidence_id: str) -> EvidenceItem:
    ev = db.get(EvidenceItem, evidence_id)
    if ev is None or ev.uploader_id != user.id:                 # only the uploader completes an upload; others cannot tell it exists
        raise CivicConnectException("EVIDENCE_NOT_FOUND", "Evidence not found or not available.", 404)
    if ev.status == "READY":
        return ev                                               # idempotent
    if ev.status == "REJECTED":
        raise CivicConnectException("EVIDENCE_REJECTED", "This upload was rejected; start a new upload.", 409)
    store = get_storage()
    size = store.size(ev.object_key)
    if size is None:
        raise CivicConnectException("UPLOAD_INCOMPLETE", "The file has not been uploaded yet.", 409)

    def reject(reason: str) -> CivicConnectException:
        ev.status = "REJECTED"
        store.delete(ev.object_key)
        db.commit()                                             # keep the rejection even though the request fails
        return CivicConnectException("EVIDENCE_REJECTED", reason, 422, {"evidence_id": ev.id})

    if size != ev.size_bytes or size > settings.MAX_UPLOAD_BYTES:
        raise reject("The uploaded size does not match what was declared.")
    data = store.get(ev.object_key)
    if hashlib.sha256(data).hexdigest() != ev.sha256:
        raise reject("The checksum of the uploaded file does not match.")
    if not sniff_ok(ev.mime_type, data[:16]):
        raise reject("The file content does not match its declared type.")
    ev.status, ev.uploaded_at = "READY", _now()
    db.flush()
    return ev


def store_direct(db: Session, user: User, *, filename: str, mime: str, data: bytes, purpose: str = "REPORT", case: CivicCase | None = None) -> EvidenceItem:
    """Single-request upload (multipart endpoint): same validation, no signed URL round trip."""
    init = UploadInit(filename=filename or "upload", mime_type=mime or "", size_bytes=max(len(data), 1), sha256=hashlib.sha256(data).hexdigest(), purpose=purpose)
    ev, _, _ = init_upload(db, user, init)
    get_storage().put(ev.object_key, data)
    ev = complete_upload(db, user, ev.id)
    if case is not None:
        ev.case_id = case.id
    return ev


def can_view(db: Session, user: User, ev: EvidenceItem) -> bool:
    from backend.services.cases import case_visible
    if ev.uploader_id == user.id:
        return True
    if not ev.case_id:
        return False
    case = db.get(CivicCase, ev.case_id)
    if case is None or not case_visible(db, user, case):
        return False
    if user.role == "citizen" and case.reporter_id != user.id:
        return False                                            # supporters never see someone else's photos
    return True


def get_visible(db: Session, user: User, evidence_id: str) -> EvidenceItem:
    ev = db.get(EvidenceItem, evidence_id)
    if ev is None or not can_view(db, user, ev):
        raise CivicConnectException("EVIDENCE_NOT_FOUND", "Evidence not found or not available.", 404)
    return ev


def serialize(ev: EvidenceItem, *, with_url: bool = False, with_location: bool = False) -> dict:
    out = {"id": ev.id, "case_id": ev.case_id, "media_type": ev.media_type, "mime_type": ev.mime_type, "size_bytes": ev.size_bytes, "status": ev.status,
           "purpose": ev.purpose, "filename": ev.filename, "captured_at": ev.captured_at, "uploaded_at": ev.uploaded_at, "location": None, "download_url": None, "expires_at": None}
    if with_location and ev.latitude is not None and ev.longitude is not None:
        out["location"] = {"latitude": ev.latitude, "longitude": ev.longitude}
    if with_url and ev.status == "READY":
        ttl = settings.SIGNED_URL_TTL_SECONDS
        out["download_url"] = get_storage().download_url(ev.object_key, ttl)
        out["expires_at"] = _now() + timedelta(seconds=ttl)
    return out


def attach(db: Session, user: User, evidence_ids: list[str], case: CivicCase, purpose: str | None = None, work_order_id: str | None = None) -> list[EvidenceItem]:
    """Link READY evidence the user uploaded (and that no case owns yet) to ``case``."""
    out = []
    for eid in dict.fromkeys(evidence_ids):
        ev = db.get(EvidenceItem, eid)
        if ev is None or ev.uploader_id != user.id:
            raise CivicConnectException("EVIDENCE_NOT_FOUND", "Evidence not found or not available.", 404, {"evidence_id": eid})
        if ev.status != "READY":
            raise CivicConnectException("EVIDENCE_NOT_READY", "Finish the upload (POST /evidence/{id}/complete) before attaching it.", 409, {"evidence_id": eid})
        if ev.case_id and ev.case_id != case.id:
            raise CivicConnectException("EVIDENCE_ALREADY_ATTACHED", "That evidence belongs to another case.", 409, {"evidence_id": eid})
        ev.case_id = case.id
        if purpose:
            ev.purpose = purpose
        if work_order_id:
            ev.work_order_id = work_order_id
        out.append(ev)
    db.flush()
    if out:
        add_event(db, case.id, "EVIDENCE_ADDED", actor_id=user.id, actor_role=user.role, metadata={"count": len(out), "purpose": purpose or out[0].purpose})
    return out


def list_for_case(db: Session, case_id: str, purpose: str | None = None) -> list[EvidenceItem]:
    q = select(EvidenceItem).where(EvidenceItem.case_id == case_id, EvidenceItem.status == "READY").order_by(EvidenceItem.created_at)
    if purpose:
        q = q.where(EvidenceItem.purpose == purpose)
    return list(db.execute(q).scalars())
