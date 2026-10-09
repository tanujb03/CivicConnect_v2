"""demo_reset: the scripted case per lifecycle stage goes through the real API, and stored embeddings survive a reset (the embedding quota is 1000 inputs a day)."""
import pytest

from backend.core.config import settings
from backend.models import CaseEmbedding
from backend.scripts import demo_reset as dr


def test_one_scripted_case_per_stage_through_the_api(staffed):
    e = staffed
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    out = dr.build_stage_cases(e.client, lambda w: e.headers(_who(w)), lambda w: e.idem(_who(w)), e.users["roads_worker"]["id"], e.where, "road_maintenance",
                               put_path=lambda url: url.replace(base, ""))
    assert [o["stage"] for o in out] == list(dr.STAGES) and [o["status"] for o in out] == list(dr.STAGES)
    assert len({o["case_number"] for o in out}) == 6
    done = {o["stage"]: o["id"] for o in out}
    wos = e.client.get("/api/v1/work-orders?limit=50", headers=e.headers("roads_op")).json()["items"]
    by_case = {w["case_id"]: w["status"] for w in wos}
    assert by_case[done["WORK_ORDER_CREATED"]] == "ASSIGNED" and by_case[done["IN_PROGRESS"]] == "IN_PROGRESS" and by_case[done["AWAITING_VERIFICATION"]] == "COMPLETED" and done["NEEDS_REVIEW"] not in by_case
    mine = e.client.get("/api/v1/work-orders", headers=e.headers("roads_worker")).json()["items"]
    assert len(mine) == 5                                                          # the field worker's own work orders exist in the real database
    detail = e.client.get(f"/api/v1/cases/{done['RESOLVED']}", headers=e.headers("roads_op")).json()
    assert detail["closed_at"] and any(x["purpose"] == "RESOLUTION" for x in detail["evidence"]) and any(x["purpose"] == "REPORT" for x in detail["evidence"])


def _who(w: str) -> str:
    return {"citizen": "alice", "citizen2": "bob", "operator": "roads_op", "worker": "roads_worker"}[w]


def test_stored_embeddings_are_dumped_and_restored_for_the_cases_that_still_exist(staffed):
    e = staffed
    from backend.tests.helpers import create_case
    a, b = create_case(e, "alice")["id"], create_case(e, "alice", description="Another pothole by the market")["id"]
    with e.session_factory() as db:
        db.add_all([CaseEmbedding(case_id=a, model="provider:m", vector=[0.6, 0.8], embedding_dim=2, embedding_model="provider:m"),
                    CaseEmbedding(case_id=b, model="provider:m", vector=[1.0, 0.0], embedding_dim=2, embedding_model="provider:m")])
        db.commit()
        saved = dr.dump_embeddings(db)
        assert sorted(r["case_id"] for r in saved) == sorted([a, b]) and saved[0]["vector"] in ([0.6, 0.8], [1.0, 0.0])
        db.query(CaseEmbedding).delete()
        db.commit()
        saved.append({**saved[0], "case_id": "case-that-was-not-reseeded"})          # a saved vector whose case no longer exists
        assert dr.missing_embeddings(db) == (2, 2)
        assert dr.restore_embeddings(db, saved) == {"restored": 2, "skipped_no_case": 1}
        row = db.get(CaseEmbedding, a)
        assert row.vector == [0.6, 0.8] and row.embedding_dim == 2 and row.embedding_model == "provider:m"
        assert dr.missing_embeddings(db) == (0, 2)


def test_help_text_says_embeddings_are_kept_and_reembedding_needs_the_flag(capsys):
    import pytest
    with pytest.raises(SystemExit):
        dr.main(["--help"])
    out = capsys.readouterr().out
    assert "EMBEDDINGS ARE KEPT" in out and "--allow-reembed" in out and "NEVER calls the embedding provider" in out


# ------------------------------------------------------------------------------------------------ safety of the command itself
class _FakeDb:
    def __init__(self, host: str | None, database: str = "civicconnect") -> None:
        from sqlalchemy.engine import make_url
        self._url = make_url(f"postgresql+psycopg2://u:secret@{host}/{database}" if host else f"sqlite:///{database}.db")

    def get_bind(self):
        return type("B", (), {"url": self._url})()


def test_a_database_on_another_machine_is_refused_unless_allowed_and_the_password_never_shows():
    from backend.services import seed
    assert seed.assert_local_target(_FakeDb("localhost")) == "localhost/civicconnect"
    assert seed.assert_local_target(_FakeDb("db")) == "db/civicconnect" and seed.assert_local_target(_FakeDb(None)).startswith("file/")
    with pytest.raises(RuntimeError, match="not a local database") as e:
        seed.assert_local_target(_FakeDb("db.abcdefgh.supabase.co"))
    assert "secret" not in str(e.value)
    assert seed.assert_local_target(_FakeDb("db.abcdefgh.supabase.co"), allow_remote=True) == "db.abcdefgh.supabase.co/civicconnect"


def test_the_spill_file_is_private_unguessable_and_restore_spill_puts_the_vectors_back(staffed, monkeypatch, capsys):
    import json
    import os
    import stat

    from backend.tests.helpers import create_case
    e = staffed
    monkeypatch.setattr(dr, "SessionLocal", e.session_factory)
    cid = create_case(e, "alice")["id"]
    rows = [{"case_id": cid, "model": "provider:m", "vector": [0.6, 0.8], "created_at": "2026-10-09T10:00:00+00:00", "embedding_dim": 2, "embedding_model": "provider:m"}]
    path = dr.write_spill(rows)
    assert path.name.startswith("demo_reset_embeddings_") and len(path.stem) > 40 and json.loads(path.read_text(encoding="utf-8")) == rows
    assert dr.write_spill(rows) != path                                                              # a fresh random name each time
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600                                            # owner only (Windows ignores the mode bits)
    assert dr.main(["--restore-spill", str(path)]) == 0 and "'restored': 1" in capsys.readouterr().out
    assert not path.exists()
    with e.session_factory() as db:
        assert db.get(CaseEmbedding, cid).vector == [0.6, 0.8]


def test_prod_is_refused_and_a_failure_after_the_wipe_keeps_the_spill_and_prints_the_command(staffed, monkeypatch, capsys):
    from backend.services import seed
    e = staffed
    monkeypatch.setattr(dr, "SessionLocal", e.session_factory)
    from backend.tests.helpers import create_case
    cid = create_case(e, "alice")["id"]
    with e.session_factory() as db:
        db.add(CaseEmbedding(case_id=cid, model="provider:m", vector=[1.0, 0.0], embedding_dim=2, embedding_model="provider:m"))
        db.commit()
    monkeypatch.setattr(settings, "ENVIRONMENT", "prod")
    assert dr.main(["--no-stage-cases"]) == 2 and "ENVIRONMENT=prod" in capsys.readouterr().err
    monkeypatch.setattr(settings, "ENVIRONMENT", "dev")

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(seed, "seed_demo_city", boom)
    with pytest.raises(RuntimeError, match="disk full"):
        dr.main(["--no-stage-cases"])
    err = capsys.readouterr().err
    assert "--restore-spill" in err and "demo_reset_embeddings_" in err
    spill = [w for w in err.split() if "demo_reset_embeddings_" in w][0].rstrip(";")
    from pathlib import Path
    assert Path(spill).exists()
    Path(spill).unlink()
