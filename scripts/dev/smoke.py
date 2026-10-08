"""End-to-end HTTP smoke test of the running API (filled in by WP11 of docs/BACKEND_BUILD_PLAN.md).

Planned usage (stdlib + httpx, against a running API with the demo accounts):

    python scripts/dev/smoke.py --base-url http://localhost:8000/api/v1

It will walk the whole loop (citizen intake -> case -> triage -> work order -> evidence -> completion -> verification -> resolved -> analytics) plus the negative checks
(forged token, other citizen, missing idempotency key, rate limit, change password, flag threshold, device registration, infected upload), print a pass/fail table and
exit non-zero on any failure. Until WP11 this stub does nothing.
"""
import sys


def main() -> int:
    print("scripts/dev/smoke.py is a stub; WP11 of docs/BACKEND_BUILD_PLAN.md implements it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
