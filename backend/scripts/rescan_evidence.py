"""Re-queue READY evidence for the malware scan.   python -m backend.scripts.rescan_evidence [--status ERROR|UNSCANNED] [--dry-run]

Sets matching READY rows back to PENDING (the scan worker then picks them up). Refuses when SCAN_ENABLED is false, and never touches INFECTED or CLEAN rows.
Prints counts only (no ids, names or file content).
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import update

from backend.core.config import settings
from backend.models import EvidenceItem

REQUEUEABLE = ("ERROR", "UNSCANNED")


def run(status: str = "ERROR", dry_run: bool = False, session_factory=None) -> dict:
    """Counts: ``matched`` rows READY with ``status``; ``requeued`` rows set to PENDING (0 on a dry run)."""
    if status not in REQUEUEABLE:
        raise ValueError(f"status must be one of {REQUEUEABLE}")
    if not settings.SCAN_ENABLED:
        raise RuntimeError("SCAN_ENABLED is false: re-queued rows would be gated as PENDING with nothing to scan them")
    if session_factory is None:
        from backend.db import session as dbs
        session_factory = dbs.SessionLocal
    with session_factory() as db:
        where = (EvidenceItem.status == "READY", EvidenceItem.scan_status == status)
        matched = db.query(EvidenceItem).filter(*where).count()
        requeued = 0
        if matched and not dry_run:
            requeued = db.execute(update(EvidenceItem).where(*where).values(scan_status="PENDING", scan_signature=None, scan_engine=None, scanned_at=None)
                                  .execution_options(synchronize_session=False)).rowcount
            from backend.services.audit import record_audit
            record_audit(db, actor_id=None, action="evidence.rescan_queued", entity_type="evidence", entity_id=None, before={"scan_status": status},
                         after={"scan_status": "PENDING", "count": requeued})
            db.commit()
    return {"status": status, "matched": matched, "requeued": requeued, "dry_run": dry_run}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Re-queue READY evidence for the malware scan.")
    ap.add_argument("--status", choices=REQUEUEABLE, default="ERROR")
    ap.add_argument("--dry-run", action="store_true", help="count only, change nothing")
    args = ap.parse_args(argv)
    try:
        out = run(args.status, args.dry_run)
    except RuntimeError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(f"matched={out['matched']} requeued={out['requeued']} dry_run={out['dry_run']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
