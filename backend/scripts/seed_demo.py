"""Load reference data and (optionally) the synthetic demo city.

    python -m backend.scripts.seed_demo --reference-only     # departments + wards (needed by a real deployment too)
    python -m backend.scripts.seed_demo                      # + 560 synthetic cases and demo accounts
    python -m backend.scripts.seed_demo --reset              # wipe all tables first (development only)
    python -m backend.scripts.seed_demo --with-embeddings    # + print the embedding plan and the command to run (default OFF; embeds NOTHING itself)

``--with-embeddings`` never calls the embedding provider: it prints the backfill's dry-run summary and the exact commands to run yourself (the probe first, then the full
run with ``--counting``), because the free quota and how it counts a batch must be decided by a person. Restoring a demo database snapshot keeps its embeddings: never re-embed
all cases after a restore (the backfill finds nothing missing, and there is no force option). ``--reset`` deletes the embeddings with the cases.
"""
from __future__ import annotations

import argparse
import sys

from backend.db.session import SessionLocal
from backend.services import seed


def embed_missing() -> int:
    """Prints the backfill's dry-run summary (no provider call, no write) and the commands to run; returns 0."""
    from backend.scripts import backfill_embeddings as bf
    bf.execute(bf.Options(dry_run=True))
    print("\nNothing was embedded. Next, yourself:")
    print(f"  1. {bf.PROBE_CMD}")
    print("  2. python -m backend.scripts.backfill_embeddings --counting per-batch   (or per-input: what AI Studio's usage page showed for step 1)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference-only", action="store_true")
    ap.add_argument("--reset", action="store_true", help="delete every row first (refused when ENVIRONMENT=prod or the database is not on this machine)")
    ap.add_argument("--allow-remote", action="store_true", help="let --reset wipe a database whose host is not localhost")
    ap.add_argument("--with-embeddings", action="store_true", help="after seeding, print the embedding plan and the commands to run (default off; embeds nothing itself)")
    a = ap.parse_args(argv)
    if a.with_embeddings and a.reference_only:
        ap.error("--with-embeddings needs the demo cases (drop --reference-only)")
    with SessionLocal() as db:
        if a.reset:
            print(f"wiping {seed.assert_local_target(db, a.allow_remote)}")
            seed.reset_all(db)
        added = seed.seed_reference(db)
        db.commit()
        print("reference data:", added)
        if a.reference_only:
            return 0
        out = seed.seed_demo_city(db)
    if out.get("skipped"):
        print("demo city already present (use --reset to reload)")
    else:
        print(f"demo city loaded: {out['cases']} synthetic cases")
        print(f"demo accounts (password for all: {out['password']}):")
        for acct in out["accounts"]:
            print(f"  {acct['role']:20s} {acct['email']}")
    return embed_missing() if a.with_embeddings else 0


if __name__ == "__main__":
    sys.exit(main())
