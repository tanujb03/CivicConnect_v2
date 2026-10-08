"""Migration 0004 on SQLite (always runs; PostgreSQL is covered by test_postgres_integration.py): ``users.must_change_password`` / ``password_changed_at`` and the
worker indexes; up, no drift, pre-existing rows backfilled to false, downgrade -1, up again. Same in-process Alembic setup as test_migration_0003.py."""
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def sqlite_url(tmp_path, monkeypatch):
    from backend.core.config import settings
    url = f"sqlite:///{(tmp_path / 'm0004.db').as_posix()}"
    monkeypatch.setattr(settings, "DATABASE_URL", url)               # alembic/env.py reads settings.SQLALCHEMY_DATABASE_URI
    return url


def _cfg() -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(REPO / "alembic"))
    return cfg


def _index_names(engine, table: str) -> set[str]:
    return {i["name"] for i in inspect(engine).get_indexes(table)}


def test_0004_adds_columns_and_indexes_backfills_false_and_round_trips(sqlite_url):
    cfg, engine = _cfg(), create_engine(sqlite_url)
    command.upgrade(cfg, "0003")
    assert "must_change_password" not in {c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as c:
        c.execute(text("INSERT INTO users (id, name, role, preferred_language, accessibility, is_active, synthetic, created_at, updated_at) "
                       "VALUES ('u-old', 'Old', 'citizen', 'en', '{}', 1, 0, '2026-10-01 00:00:00', '2026-10-01 00:00:00')"))

    command.upgrade(cfg, "head")
    command.check(cfg)                                                # models and migrated schema agree
    cols = {c["name"]: c for c in inspect(engine).get_columns("users")}
    assert {"must_change_password", "password_changed_at"} <= set(cols) and cols["must_change_password"]["nullable"] is False and cols["password_changed_at"]["nullable"] is True
    with engine.begin() as c:
        assert c.execute(text("SELECT must_change_password, password_changed_at FROM users WHERE id = 'u-old'")).one() == (0, None)   # nobody is locked out by the upgrade
    assert "ix_device_tokens_user_active" in _index_names(engine, "device_tokens")
    assert "ix_notif_push_status" in _index_names(engine, "notifications")
    assert "ix_evidence_scan_status" in _index_names(engine, "evidence_items")
    assert {"ix_case_flags_case_status", "ix_case_flags_case_kind", "ix_case_flags_status"} <= _index_names(engine, "case_flags")
    assert any(sorted(u["column_names"]) == ["case_id", "kind", "user_id"] for u in inspect(engine).get_unique_constraints("case_flags"))   # uq_case_flag from 0003 is still there

    command.downgrade(cfg, "-1")
    assert not {"must_change_password", "password_changed_at"} & {c["name"] for c in inspect(engine).get_columns("users")}
    assert "ix_notif_push_status" not in _index_names(engine, "notifications")
    with engine.begin() as c:
        assert c.execute(text("SELECT count(*) FROM users")).scalar() == 1                          # the data survived
    command.upgrade(cfg, "head")
    command.check(cfg)
    engine.dispose()
