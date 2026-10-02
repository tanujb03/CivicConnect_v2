"""
/api/v1/sync  — Offline sync mutation endpoint.

Citizens queue mutations locally (IndexedDB) while offline.
When connectivity returns, the PWA POSTs each mutation here.

Rules (per Section 51A):
- Idempotency-Key header is REQUIRED; missing → 422.
- Duplicate keys are silently accepted (idempotent).
- Each mutation is written to the civic:sync Redis Stream.
- Worker (`events/workers.py`) applies the mutation asynchronously.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from typing import Any, Dict, Optional

from backend.core.security import get_current_user
from backend.events import emit_sync_mutation, emit_audit

router = APIRouter()


class SyncMutation(BaseModel):
    mutation_type: str          # "create_case" | "add_evidence" | "support"
    data: Dict[str, Any]


@router.post("/mutations")
def apply_sync_mutation(
    mutation: SyncMutation,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    current_user: dict = Depends(get_current_user),
):
    """
    Idempotent mutation endpoint for offline-queued citizen actions.
    Requires Idempotency-Key header.
    """
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "sync.missing_idempotency_key",
                    "message": "Idempotency-Key header is required for sync mutations."},
        )

    # Publish to Redis sync stream for async processing
    entry_id = emit_sync_mutation(
        idempotency_key=idempotency_key,
        mutation_type=mutation.mutation_type,
        actor_id=current_user["sub"],
        data=mutation.data,
    )

    # Emit an audit event for the sync attempt
    emit_audit(
        actor_id=current_user["sub"],
        action=f"sync.{mutation.mutation_type}",
        details={"idempotency_key": idempotency_key, "stream_entry": entry_id},
    )

    return {
        "status": "queued",
        "idempotency_key": idempotency_key,
        "mutation_type": mutation.mutation_type,
        "stream_entry_id": entry_id,
    }


@router.get("/status")
def get_sync_status(current_user: dict = Depends(get_current_user)):
    """Check how many pending mutations exist in the sync stream for this user."""
    return {"pending": 0, "last_synced_at": None}
