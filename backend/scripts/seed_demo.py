"""Load reference data and (optionally) the synthetic demo city.

    python -m backend.scripts.seed_demo --reference-only     # departments + wards (needed by a real deployment too)
    python -m backend.scripts.seed_demo                      # + 560 synthetic cases and demo accounts
    python -m backend.scripts.seed_demo --reset              # wipe all tables first (development only)
"""
from __future__ import annotations

import argparse
import sys

from backend.db.session import SessionLocal
from backend.services import seed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference-only", action="store_true")
    ap.add_argument("--reset", action="store_true", help="delete every row first (refused when ENVIRONMENT=prod)")
    a = ap.parse_args(argv)
    with SessionLocal() as db:
        if a.reset:
            seed.reset_all(db)
        added = seed.seed_reference(db)
        db.commit()
        print("reference data:", added)
        if a.reference_only:
            return 0
        out = seed.seed_demo_city(db)
    if out.get("skipped"):
        print("demo city already present (use --reset to reload)")
        return 0
    print(f"demo city loaded: {out['cases']} synthetic cases")
    print(f"demo accounts (password for all: {out['password']}):")
    for acct in out["accounts"]:
        print(f"  {acct['role']:20s} {acct['email']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
