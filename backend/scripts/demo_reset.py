"""Reset the DEVELOPMENT database to a known demo state: the synthetic city (reference data, 560 cases, demo accounts) plus one scripted case per lifecycle stage.

    python -m backend.scripts.demo_reset                    # rebuild, keep the stored embeddings, add the five scripted cases
    python -m backend.scripts.demo_reset --no-stage-cases   # only the city
    python -m backend.scripts.demo_reset --allow-reembed    # also DROP the stored embeddings (see below)

The scripted cases go through the real HTTP API in this process (so they have evidence, a timeline, audit rows and notifications): a case awaiting triage, one with a work order
assigned to a field worker, one in progress (started by the field worker), one awaiting the citizen's verification, one reopened after a "NO", one resolved. No model is called: the AI job queue is
switched off and the provider keys are removed for the run, so every AI step takes its rules-only path.

EMBEDDINGS ARE KEPT. The free embedding quota is 1000 inputs a day (30K tokens a minute), so a reset must never re-embed the city: the stored vectors of every case that still exists
after the reseed (the dataset ids are fixed) are put back, pgvector column included, and only the rows that are still missing an embedding (the new scripted cases) are counted and
reported. This script NEVER calls the embedding provider. ``--allow-reembed`` is the only way to discard the stored vectors (it prints the backfill commands to run yourself, one probe
first; see docs/AI_LIVE_CHECK.md). The vectors are written to a private (owner-only) file in the temp directory before anything is deleted and removed after the restore; if the run
fails after the wipe the file is kept and the exact command is printed: ``python -m backend.scripts.demo_reset --restore-spill <file>`` puts the vectors back into the current
database and touches nothing else.

Refused when ENVIRONMENT=prod, and when the database host is not this machine unless --allow-remote. Prints the target (host/database, never the password) before it deletes
every row of every table.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select, text

from backend.db.session import SessionLocal
from backend.models import CaseEmbedding, CivicCase
from backend.services import seed

JPEG = b"\xff\xd8\xff\xe0" + b"\x00\x10JFIF\x00" + b"civicconnect-demo-image-bytes" * 8
STAGES = ("NEEDS_REVIEW", "WORK_ORDER_CREATED", "AWAITING_VERIFICATION", "REOPENED", "RESOLVED", "IN_PROGRESS")


# ---------------------------------------------------------------------------------------------- embeddings
def _is_pg(db) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _has_vec(db) -> bool:
    return _is_pg(db) and bool(db.execute(text("SELECT 1 FROM information_schema.columns WHERE table_name = 'case_embeddings' AND column_name = 'embedding_vec'")).first())


def dump_embeddings(db) -> list[dict[str, Any]]:
    """Every stored embedding row (json vector + the pgvector value as text), read before the reset."""
    vec = ", embedding_vec::text AS vec_text" if _has_vec(db) else ""
    rows = db.execute(text(f"SELECT case_id, model, vector, created_at, embedding_dim, embedding_model{vec} FROM case_embeddings")).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        c = d.get("created_at")
        d["created_at"] = c.isoformat() if hasattr(c, "isoformat") else c             # SQLite hands back a string, PostgreSQL a datetime
        if isinstance(d["vector"], str):
            d["vector"] = json.loads(d["vector"])
        out.append(d)
    return out


def restore_embeddings(db, rows: list[dict[str, Any]]) -> dict[str, int]:
    """Put the saved rows back for the cases that exist now; returns {restored, skipped_no_case}."""
    existing = set(db.execute(select(CivicCase.id)).scalars())
    has_vec = _has_vec(db)
    restored = skipped = 0
    for r in rows:
        if r["case_id"] not in existing:
            skipped += 1
            continue
        db.add(CaseEmbedding(case_id=r["case_id"], model=r["model"], vector=r["vector"], embedding_dim=r.get("embedding_dim"), embedding_model=r.get("embedding_model"),
                             created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else None))
        restored += 1
    db.flush()
    if has_vec:
        for r in rows:
            if r["case_id"] in existing and r.get("vec_text"):
                db.execute(text("UPDATE case_embeddings SET embedding_vec = CAST(:v AS vector) WHERE case_id = :c"), {"v": r["vec_text"], "c": r["case_id"]})
    db.commit()
    return {"restored": restored, "skipped_no_case": skipped}


def missing_embeddings(db) -> tuple[int, int]:
    """(cases without an embedding, cases)."""
    n = db.execute(text("SELECT count(*) FROM civic_cases c WHERE NOT EXISTS (SELECT 1 FROM case_embeddings e WHERE e.case_id = c.id)")).scalar_one()
    return int(n), int(db.execute(text("SELECT count(*) FROM civic_cases")).scalar_one())


# ---------------------------------------------------------------------------------------------- scripted cases
def build_stage_cases(client, auth: Callable[[str], dict[str, str]], idem: Callable[[str], dict[str, str]], worker_id: str, where: dict[str, float], department_id: str,
                      put_path: Callable[[str], str] = lambda url: url) -> list[dict[str, Any]]:
    """One case per lifecycle stage through the API. ``auth(who)`` / ``idem(who)`` give headers for who in citizen, citizen2, operator, worker; ``put_path`` maps a signed upload URL to
    what ``client.put`` takes (the tests strip the public base URL). Returns [{stage, id, case_number, status}]."""
    import hashlib

    def up(who: str, data: bytes, name: str, purpose: str = "REPORT") -> str:
        i = client.post("/api/v1/evidence/upload-init", headers=idem(who), json={"filename": name, "mime_type": "image/jpeg", "size_bytes": len(data),
                                                                                   "sha256": hashlib.sha256(data).hexdigest(), "purpose": purpose, "source": "SMARTPHONE"})
        assert i.status_code == 201, f"upload-init {i.status_code} {i.text[:200]}"
        b = i.json()
        p = client.put(put_path(b["upload_url"]), content=data, headers={"Content-Type": "image/jpeg"})
        assert p.status_code in (200, 204), f"upload PUT {p.status_code}"
        d = client.post(f"/api/v1/evidence/{b['evidence_id']}/complete", headers=auth(who))
        assert d.status_code == 200, f"upload complete {d.status_code} {d.text[:200]}"
        return d.json()["id"]

    def need(r, code: tuple[int, ...], what: str) -> dict:
        assert r.status_code in code, f"{what}: HTTP {r.status_code} {r.text[:240]}"
        return r.json()

    out: list[dict[str, Any]] = []
    scenes = [("citizen", "Deep pothole in front of the bus stop on the main road, buses are swerving around it", 0.0000),
              ("citizen", "Large pothole outside the primary school gate, two children fell last week", 0.0006),
              ("citizen2", "Broken road surface near the market entrance, vehicles slow down sharply", 0.0012),
              ("citizen2", "Pothole at the junction near the pharmacy, filled badly last month and open again", 0.0018),
              ("citizen", "Sunken patch on the service road behind the temple, water collects after rain", 0.0024),
              ("citizen2", "Crater-sized pothole on the ring road slip lane, two-wheelers skid on the loose gravel", 0.0030)]
    for stage, (who, desc, dlon) in zip(STAGES, scenes):
        photo = up(who, JPEG + stage.encode(), f"{stage.lower()}.jpg")
        created = need(client.post("/api/v1/cases", headers=idem(who), json={"description": desc, "category": "roads", "subcategory": "pothole", "language": "en",
                                                                              "location": {"latitude": where["latitude"], "longitude": where["longitude"] + dlon},
                                                                              "evidence_ids": [photo]}), (201,), f"create {stage}")["case"]
        cid = created["id"]
        if stage != "NEEDS_REVIEW":
            need(client.post(f"/api/v1/cases/{cid}/triage/decision", headers=idem("operator"), json={"severity": "HIGH", "priority": "HIGH", "department_id": department_id,
                                                                                                    "sla_hours": 48, "reason": "scripted demo case"}), (200,), f"triage {stage}")
            wo = need(client.post(f"/api/v1/cases/{cid}/work-orders", headers=idem("operator"),
                                  json={"assignee_id": worker_id, "instructions": "Fill and compact the pothole, photograph the finished surface", "due_at": "2099-01-01T10:00:00Z"}),
                      (201,), f"work order {stage}")
            if stage != "WORK_ORDER_CREATED":
                need(client.post(f"/api/v1/work-orders/{wo['id']}/start", headers=idem("worker")), (200,), f"start {stage}")
            if stage not in ("WORK_ORDER_CREATED", "IN_PROGRESS"):
                proof = up("worker", JPEG + b"after" + stage.encode(), f"after_{stage.lower()}.jpg", purpose="RESOLUTION")
                need(client.post(f"/api/v1/work-orders/{wo['id']}/complete", headers=idem("worker"), json={"notes": "Pothole filled and compacted", "resolution_evidence_ids": [proof]}),
                     (200,), f"complete {stage}")
            if stage in ("REOPENED", "RESOLVED"):
                result = "NO" if stage == "REOPENED" else "YES"
                need(client.post(f"/api/v1/cases/{cid}/verification", headers=idem(who), json={"result": result, "comment": "still broken" if result == "NO" else "road is smooth again"}),
                     (201,), f"verification {stage}")
        status = need(client.get(f"/api/v1/cases/{cid}", headers=auth("operator")), (200,), f"read {stage}")["status"]
        assert status == stage, f"stage {stage} ended in {status}"
        out.append({"stage": stage, "id": cid, "case_number": created["case_number"], "status": status})
    return out


def _run_stage_cases() -> list[dict[str, Any]]:
    import uuid

    from fastapi.testclient import TestClient

    from backend.ai_gateway import configure_gateway, deps, envfile
    from backend.ai_gateway.sql import build_sql_gateway
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CLOUDFLARE_API_TOKEN"):     # rules only: the after-commit AI reviews must not call a provider
        os.environ.pop(k, None)
    envfile.load_env_file = deps.load_env_file = lambda *a, **k: []               # type: ignore[assignment]
    configure_gateway(build_sql_gateway())                                        # what the app's lifespan does; triage and fusion look cases up through it
    import backend.events as ev
    from backend.core.config import settings
    from backend.events import publisher
    from backend.main import app
    ev.emit_ai_job = publisher.emit_ai_job = lambda *a, **k: None                # type: ignore[assignment]  # no AI job: the run must not touch any quota
    dept = "road_maintenance"
    domain = "demo.civicconnect.test"
    client = TestClient(app, raise_server_exceptions=False)
    tokens: dict[str, str] = {}
    for who, email in (("citizen", f"citizen001@{domain}"), ("citizen2", f"citizen002@{domain}"), ("operator", f"operator.{dept}@{domain}"), ("worker", f"worker.{dept}@{domain}")):
        r = client.post("/api/v1/auth/login", json={"identifier": email, "password": settings.DEMO_PASSWORD})
        assert r.status_code == 200, f"demo sign-in of {who} failed (HTTP {r.status_code}): is the demo city seeded?"
        tokens[who] = r.json()["access_token"]
        if who == "worker":
            wid = r.json()["user"]["id"]
    head = lambda who: {"Authorization": f"Bearer {tokens[who]}"}                  # noqa: E731
    idem = lambda who: {**head(who), "Idempotency-Key": str(uuid.uuid4())}         # noqa: E731
    with SessionLocal() as db:
        c = db.query(CivicCase).filter(CivicCase.department_id == dept).first()
        where = {"latitude": c.latitude, "longitude": c.longitude}
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return build_stage_cases(client, head, idem, wid, where, dept, put_path=lambda url: url.replace(base, "") if url.startswith(base) else url)


# ---------------------------------------------------------------------------------------------- the command
def write_spill(rows: list[dict[str, Any]]) -> Path:
    """Owner-only file with an unguessable name in the temp directory."""
    path = Path(tempfile.gettempdir()) / f"demo_reset_embeddings_{uuid.uuid4().hex}.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(rows, f)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-stage-cases", action="store_true", help="only the synthetic city, no scripted lifecycle cases")
    ap.add_argument("--allow-reembed", action="store_true", help="discard the stored embeddings (the quota is then spent again by the backfill YOU run); without it they are kept")
    ap.add_argument("--allow-remote", action="store_true", help="allow a database whose host is not localhost")
    ap.add_argument("--restore-spill", type=Path, default=None, metavar="FILE", help="after a failed run: put the vectors of that file back into the current database and stop (no wipe)")
    a = ap.parse_args(argv)
    from backend.core.config import settings
    if settings.ENVIRONMENT.lower() == "prod":
        print("REFUSED: ENVIRONMENT=prod", file=sys.stderr)
        return 2
    t0 = time.time()
    if a.restore_spill is not None:
        with SessionLocal() as db:
            try:
                seed.assert_local_target(db, a.allow_remote)
            except RuntimeError as e:
                print(f"REFUSED: {e}", file=sys.stderr)
                return 2
            print("embeddings restored:", restore_embeddings(db, json.loads(a.restore_spill.read_text(encoding="utf-8"))))
        a.restore_spill.unlink(missing_ok=True)
        return 0
    saved: list[dict[str, Any]] = []
    spill: Path | None = None
    with SessionLocal() as db:
        try:
            target = seed.assert_local_target(db, a.allow_remote)
        except RuntimeError as e:
            print(f"REFUSED: {e}", file=sys.stderr)
            return 2
        print(f"target: {target} (every row of every table will be deleted)")
        if not a.allow_reembed:
            saved = dump_embeddings(db)
            if saved:
                spill = write_spill(saved)
                print(f"kept {len(saved)} stored embeddings in memory and in {spill}")
        else:
            n = db.execute(text("SELECT count(*) FROM case_embeddings")).scalar_one()
            print(f"--allow-reembed: {n} stored embeddings will be DISCARDED")
        try:
            seed.reset_all(db)
            seed.seed_reference(db)
            db.commit()
            out = seed.seed_demo_city(db)
            db.commit()
            print(f"demo city loaded: {out.get('cases')} synthetic cases")
            if saved:
                print("embeddings restored:", restore_embeddings(db, saved))
        except Exception:
            if spill is not None:
                print(f"FAILED after the wipe. Your embeddings are in {spill}; once the demo city is loaded again run: "
                      f"python -m backend.scripts.demo_reset --restore-spill {spill}", file=sys.stderr)
            raise
        if spill is not None:
            spill.unlink(missing_ok=True)
    staged: list[dict[str, Any]] = []
    if not a.no_stage_cases:
        staged = _run_stage_cases()
        for s in staged:
            print(f"  scripted {s['stage']:22s} {s['case_number']}  {s['id']}")
    with SessionLocal() as db:
        miss, total = missing_embeddings(db)
    print(f"cases without an embedding: {miss} of {total}" + (" (the scripted cases; they are embedded one input each when the API's worker runs, or by the backfill)" if miss else ""))
    if a.allow_reembed:
        print("Next, yourself (this script never calls the provider): python -m backend.scripts.backfill_embeddings --dry-run, then the probe and the full run described in docs/AI_LIVE_CHECK.md")
    print(f"done in {time.time() - t0:.1f} s; demo password for every account: see DEMO_PASSWORD ({os.environ.get('DEMO_PASSWORD', 'development default')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
