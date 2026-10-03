"""Engine / session factory. Works on PostgreSQL (production, PostGIS) and SQLite (fast tests); ``configure_database`` rebinds both at runtime."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import settings

Base = declarative_base()


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        memory = ":memory:" in url or url in ("sqlite://", "sqlite:///")
        kw: dict = {"connect_args": {"check_same_thread": False, "timeout": 30}}
        if memory:
            kw["poolclass"] = StaticPool          # one shared in-memory database for every session
        eng = create_engine(url, **kw)

        @event.listens_for(eng, "connect")
        def _pragmas(dbapi_conn, _):             # SQLite ignores foreign keys unless asked; WAL lets readers and the single writer coexist (file databases)
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            if not memory:
                dbapi_conn.execute("PRAGMA journal_mode=WAL")

        return eng
    return create_engine(url, pool_pre_ping=True)


engine: Engine = make_engine(settings.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


def configure_database(url: str) -> Engine:
    """Point the process at another database (tests, scripts). Existing sessions keep their old bind."""
    global engine
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
    return engine


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope():
    """Short transaction for code that runs outside a request (AI gateway ports, workers, scripts)."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
