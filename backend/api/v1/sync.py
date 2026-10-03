"""/api/v1/sync: offline synchronisation (§51A.16).

Citizens queue mutations locally (IndexedDB) while offline; when connectivity returns the PWA posts the ordered batch here. Every mutation carries its own
``idempotency_key`` and is applied at most once: a retried batch returns ``ALREADY_APPLIED`` and never creates a second case or side effect.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.security import current_user
from backend.db.session import get_db
from backend.models import User
from backend.schemas.sync import SyncChanges, SyncRequest, SyncResponse
from backend.services import sync as sync_service

router = APIRouter()


@router.post("/mutations", response_model=SyncResponse)
def apply_sync_mutations(body: SyncRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    results = sync_service.process(db, user, body.mutations)
    db.commit()
    return {"results": results, "server_cursor": sync_service.encode_cursor(sync_service.max_visible_seq(db, user))}


@router.get("/changes", response_model=SyncChanges)
def get_sync_changes(cursor: Optional[str] = None, limit: int = Query(default=100, ge=1, le=500), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Authorized changes since ``cursor`` (omit it for a first full pull); page on with ``server_cursor`` while ``has_more``."""
    return sync_service.changes_since(db, user, cursor, limit)
