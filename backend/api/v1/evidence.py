from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.api.deps import IdempotencyHeader, idempotent
from backend.core.config import settings
from backend.core.exceptions import CivicConnectException
from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import EvidenceItem, User
from backend.schemas.evidence import EvidenceOut, UploadInit, UploadInitOut
from backend.services import cases as case_service
from backend.services import evidence as evidence_service
from backend.storage import LocalStorage, get_storage, verify_blob_token

router = APIRouter()


def _forbid_overlooker(user: User) -> None:
    if user.role == "overlooker":
        raise CivicConnectException("AUTH_FORBIDDEN", "Your role may not upload evidence.", 403)


@router.post("/upload-init", response_model=UploadInitOut, status_code=201)
def upload_init(body: UploadInit, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """§51A.6: creates the upload session. The client then PUTs the file bytes to ``upload_url`` and calls ``/evidence/{id}/complete``."""
    _forbid_overlooker(user)

    def handler():
        ev, url, expires = evidence_service.init_upload(db, user, body)
        return 201, {"evidence_id": ev.id, "upload_url": url, "expires_at": expires, "method": "PUT", "headers": {"Content-Type": ev.mime_type}}, ev.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path="/evidence/upload-init", payload=body.model_dump(mode="json"), handler=handler)


@router.post("", response_model=EvidenceOut, status_code=201)
@router.post("/", response_model=EvidenceOut, status_code=201, include_in_schema=False)
def upload_direct(response: Response, file: UploadFile = File(...), case_id: Optional[str] = Form(default=None), purpose: str = Form(default="REPORT"),
                  idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Single-request multipart upload (small files, development): same validation as the signed-URL flow."""
    _forbid_overlooker(user)
    if purpose not in ("REPORT", "RESOLUTION", "VERIFICATION"):
        raise CivicConnectException("VALIDATION_ERROR", "Unknown purpose.", 422, {"field": "purpose"})
    data = file.file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise CivicConnectException("PAYLOAD_TOO_LARGE", "The file is larger than the allowed size.", 413, {"max_bytes": settings.MAX_UPLOAD_BYTES})

    def handler():
        case = case_service.get_visible_case(db, user, case_id) if case_id else None
        ev = evidence_service.store_direct(db, user, filename=file.filename or "upload", mime=(file.content_type or "").lower(), data=data, purpose=purpose, case=case)
        return 201, evidence_service.serialize(ev), ev.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path="/evidence", payload={"name": file.filename, "size": len(data), "case_id": case_id, "purpose": purpose},
                      handler=handler, required=False)


@router.post("/{evidence_id}/complete", response_model=EvidenceOut)
def complete_upload(evidence_id: str, response: Response, idempotency_key: Optional[str] = IdempotencyHeader, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Server validates object existence, checksum, MIME type and size before the evidence becomes available to workflows (§51A.6)."""
    def handler():
        ev = evidence_service.complete_upload(db, user, evidence_id)
        return 200, evidence_service.serialize(ev), ev.id
    return idempotent(db, response, user_id=user.id, key=idempotency_key, method="POST", path=f"/evidence/{evidence_id}/complete", payload={}, handler=handler, required=False)


@router.get("/{evidence_id}", response_model=EvidenceOut)
def get_evidence(evidence_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Metadata plus a short-lived signed retrieval URL when the caller may see the evidence."""
    ev = evidence_service.get_visible(db, user, evidence_id)
    return evidence_service.serialize(ev, with_url=True, with_location=user.role in case_service.STAFF_ROLES or ev.uploader_id == user.id)


# ---------------------------------------------------------------------------------------------------------------- signed blob endpoints (LocalStorage only)
def _local() -> LocalStorage:
    store = get_storage()
    if not isinstance(store, LocalStorage):
        raise CivicConnectException("NOT_FOUND", "Not found.", 404)
    return store


@router.put("/blob/{token}", include_in_schema=False)
async def put_blob(token: str, request: Request):
    store = _local()
    claims = verify_blob_token(token, "PUT")
    if claims is None:
        raise CivicConnectException("SIGNED_URL_INVALID", "The upload link is invalid or expired.", 403)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.MAX_UPLOAD_BYTES:
        raise CivicConnectException("PAYLOAD_TOO_LARGE", "The file is larger than the allowed size.", 413)
    if claims.get("t") and (request.headers.get("content-type", "").split(";")[0].strip().lower() != claims["t"]):
        raise CivicConnectException("UNSUPPORTED_MEDIA_TYPE", "Content-Type does not match the upload session.", 415, {"expected": claims["t"]})
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > settings.MAX_UPLOAD_BYTES:
            raise CivicConnectException("PAYLOAD_TOO_LARGE", "The file is larger than the allowed size.", 413)
    store.put(claims["k"], body)
    return Response(status_code=204)


@router.get("/blob/{token}", include_in_schema=False)
def get_blob(token: str, db: Session = Depends(get_db)):
    store = _local()
    claims = verify_blob_token(token, "GET")
    if claims is None:
        raise CivicConnectException("SIGNED_URL_INVALID", "The download link is invalid or expired.", 403)
    ev = db.execute(select(EvidenceItem).where(EvidenceItem.object_key == claims["k"])).scalar_one_or_none()
    try:
        data = store.get(claims["k"])
    except FileNotFoundError:
        raise CivicConnectException("NOT_FOUND", "Not found.", 404)
    return Response(content=data, media_type=(ev.mime_type if ev else "application/octet-stream"),
                    headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store", "Content-Disposition": "inline"})
