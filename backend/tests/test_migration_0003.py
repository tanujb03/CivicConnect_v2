"""Migration 0003 on SQLite (always runs; the PostgreSQL / pgvector side is in test_postgres_integration.py):
up, no drift, backfill of pre-existing rows, defaults of new rows, constraints, downgrade -1, up again; plus the model constants / schema literals and the
readiness flag. Alembic runs in-process with an explicit Config (no alembic.ini, so env.py does not reconfigure the logging of the other tests)."""
from pathlib import Path
from typing import get_args

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def sqlite_url(tmp_path, monkeypatch):
    from backend.core.config import settings
    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)               # alembic/env.py reads settings.SQLALCHEMY_DATABASE_URI
    return url


def _cfg() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(REPO / "alembic"))
    return cfg


def _cols(engine, table):
    return {c["name"] for c in inspect(engine).get_columns(table)}


def test_upgrade_backfill_defaults_constraints_downgrade_and_upgrade_again(sqlite_url):
    cfg, engine = _cfg(), create_engine(sqlite_url)
    command.upgrade(cfg, "0002")
    assert not {"scan_status", "push_status", "embedding_dim"} & (_cols(engine, "evidence_items") | _cols(engine, "notifications") | _cols(engine, "case_embeddings"))
    with engine.begin() as c:                                         # rows that exist BEFORE 0003 (SQLite does not enforce foreign keys by default)
        c.execute(text("INSERT INTO evidence_items (id, uploader_id, purpose, object_key, filename, media_type, mime_type, size_bytes, sha256, status, created_at) "
                       "VALUES ('ev-old', 'u1', 'REPORT', 'k/old', 'a.jpg', 'IMAGE', 'image/jpeg', 1, '00', 'READY', '2026-10-01 00:00:00')"))
        c.execute(text("INSERT INTO notifications (id, user_id, type, payload, created_at) VALUES ('n-old', 'u1', 'CASE_UPDATED', '{}', '2026-10-01 00:00:00')"))
        c.execute(text("INSERT INTO case_embeddings (case_id, model, vector, created_at) VALUES ('c1', 'legacy', '[0.1]', '2026-10-01 00:00:00')"))

    command.upgrade(cfg, "head")
    command.check(cfg)                                                # raises when the models and the migrated schema differ
    insp = inspect(engine)
    assert {"system_settings", "device_tokens", "case_flags"} <= set(insp.get_table_names())
    assert {"scan_status", "scan_engine", "scan_signature", "scanned_at"} <= _cols(engine, "evidence_items")
    assert {"push_status", "push_attempts", "pushed_at", "push_receipt_id"} <= _cols(engine, "notifications")
    assert {"embedding_dim", "embedding_model"} <= _cols(engine, "case_embeddings") and "embedding_vec" not in _cols(engine, "case_embeddings")   # pgvector is PostgreSQL-only
    assert {"ix_case_flags_case_kind", "ix_case_flags_status"} <= {i["name"] for i in insp.get_indexes("case_flags")}
    assert "ix_device_tokens_user_id" in {i["name"] for i in insp.get_indexes("device_tokens")}

    with engine.begin() as c:
        assert c.execute(text("SELECT scan_status FROM evidence_items WHERE id = 'ev-old'")).scalar() == "UNSCANNED"          # backfilled
        assert c.execute(text("SELECT push_status, push_attempts FROM notifications WHERE id = 'n-old'")).one() == ("NONE", 0)
        assert c.execute(text("SELECT embedding_dim, embedding_model FROM case_embeddings WHERE case_id = 'c1'")).one() == (None, None)
        c.execute(text("INSERT INTO evidence_items (id, uploader_id, purpose, object_key, filename, media_type, mime_type, size_bytes, sha256, status, created_at) "
                       "VALUES ('ev-new', 'u1', 'REPORT', 'k/new', 'b.jpg', 'IMAGE', 'image/jpeg', 1, '00', 'PENDING', '2026-10-04 00:00:00')"))
        assert c.execute(text("SELECT scan_status FROM evidence_items WHERE id = 'ev-new'")).scalar() == "PENDING"            # default of NEW rows
        c.execute(text("INSERT INTO case_flags (id, case_id, user_id, kind, created_at) VALUES ('f1', 'c1', 'u1', 'OUTDATED', '2026-10-04 00:00:00')"))
        assert c.execute(text("SELECT status FROM case_flags WHERE id = 'f1'")).scalar() == "OPEN"
    for sql in ("INSERT INTO case_flags (id, case_id, user_id, kind, created_at) VALUES ('f2', 'c1', 'u1', 'OUTDATED', '2026-10-04 00:00:00')",         # duplicate (case, user, kind)
                "INSERT INTO case_flags (id, case_id, user_id, kind, created_at) VALUES ('f3', 'c1', 'u1', 'SPAM', '2026-10-04 00:00:00')",             # kind outside the list
                "INSERT INTO case_flags (id, case_id, user_id, kind, status, created_at) VALUES ('f4', 'c1', 'u1', 'INCORRECT', 'DONE', '2026-10-04 00:00:00')"):
        with pytest.raises(IntegrityError), engine.begin() as c:
            c.execute(text(sql))
    insert_token = "INSERT INTO device_tokens (id, user_id, platform, expo_push_token, created_at, last_seen_at) VALUES ('{}', 'u1', 'ios', 'ExponentPushToken[x]', 'now', 'now')"
    with engine.begin() as c:
        c.execute(text(insert_token.format("d1")))
    with pytest.raises(IntegrityError), engine.begin() as c:                                                                  # expo_push_token is unique
        c.execute(text(insert_token.format("d2")))

    command.downgrade(cfg, "0002")                                    # 0003 and the later 0004 go; the data must survive
    assert not {"scan_status", "push_status", "embedding_dim", "embedding_model"} & (_cols(engine, "evidence_items") | _cols(engine, "notifications") | _cols(engine, "case_embeddings"))
    assert not {"system_settings", "device_tokens", "case_flags"} & set(inspect(engine).get_table_names())
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM evidence_items")).scalar() == 2                                           # the data survived the downgrade
    command.upgrade(cfg, "head")
    command.check(cfg)
    with engine.begin() as c:
        assert dict(c.execute(text("SELECT id, scan_status FROM evidence_items")).all()) == {"ev-old": "UNSCANNED", "ev-new": "UNSCANNED"}   # a re-upgrade backfills again
    engine.dispose()


def test_orm_defaults_and_constants_match_the_migration():
    from backend.models import FLAG_KINDS, FLAG_STATUSES, PUSH_STATUSES, SCAN_STATUSES, CaseFlag, EvidenceItem, Notification
    from backend.schemas.platform import CaseFlagOut, CaseFlagResolveIn
    assert SCAN_STATUSES == ("PENDING", "CLEAN", "INFECTED", "UNSCANNED", "ERROR") and PUSH_STATUSES == ("NONE", "PENDING", "SENT", "FAILED", "SKIPPED")
    assert get_args(CaseFlagOut.model_fields["kind"].annotation) == FLAG_KINDS and get_args(CaseFlagOut.model_fields["status"].annotation) == FLAG_STATUSES
    assert get_args(CaseFlagResolveIn.model_fields["status"].annotation) == ("UPHELD", "DISMISSED")
    assert EvidenceItem.__table__.c.scan_status.default.arg == "PENDING" and Notification.__table__.c.push_status.default.arg == "NONE"
    assert CaseFlag.__table__.c.status.default.arg == "OPEN"


def test_readiness_reports_vector_search_false_without_pgvector(env):
    body = env.client.get("/api/v1/health/ready").json()                # the unit-test database is SQLite: no pgvector
    assert body["status"] == "ready" and body["vector_search"] is False
