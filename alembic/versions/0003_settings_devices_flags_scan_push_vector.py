"""system_settings, device_tokens, case_flags; evidence scan and notification push columns; pgvector (PostgreSQL only, when available)

Revision ID: 0003
Revises: 0002

Works on PostgreSQL and SQLite (batch operations; the pgvector part is PostgreSQL-only).

pgvector (https://github.com/pgvector/pgvector, README "Can I store vectors with different dimensions in the same column?"): ``case_embeddings.embedding_vec`` is
an untyped-dimension ``vector`` because the final embedding model (multilingual-e5-small = 384 or e5-base = 768) is not decided yet. A fixed-dimension index needs an
expression index plus a partial predicate, so there is one HNSW cosine index per candidate dimension. To use them a query MUST repeat the predicate and the cast:

    SELECT case_id FROM case_embeddings
    WHERE embedding_dim = 384
    ORDER BY embedding_vec::vector(384) <=> CAST(:query AS vector(384)) LIMIT 10;

Without the extension (not installed on the server, or not permitted) only ``embedding_dim`` and ``embedding_model`` are added, a warning is logged and
``GET /api/v1/health/ready`` reports ``vector_search: false``; the JSON ``vector`` column keeps working. The downgrade does not drop the ``vector`` extension itself
(other database objects may use it; migration 0002 does the same for PostGIS).
"""
import logging
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")

JSONType = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
VECTOR_DIMS = (384, 768)


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _vector_available() -> bool:
    return bool(op.get_bind().execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")).scalar())


def _enable_vector() -> bool:
    """CREATE EXTENSION inside a savepoint: a missing privilege degrades to 'no vector search' instead of failing the whole migration."""
    try:
        with op.get_bind().begin_nested():
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        return True
    except sa.exc.DBAPIError as exc:
        log.warning("0003: CREATE EXTENSION vector failed (%s); continuing WITHOUT pgvector.", str(exc.orig).strip().splitlines()[0])
        return False


def upgrade() -> None:
    # --- 1. system_settings
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value_json", JSONType, nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("key"),
    )

    # --- 2. device_tokens
    op.create_table(
        "device_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("expo_push_token", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=True),
        sa.Column("locale", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expo_push_token"),
    )
    op.create_index(op.f("ix_device_tokens_user_id"), "device_tokens", ["user_id"], unique=False)

    # --- 3. case_flags
    op.create_table(
        "case_flags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("resolved_by", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('STILL_EXISTS', 'OUTDATED', 'INCORRECT', 'INAPPROPRIATE')", name="ck_case_flags_kind"),
        sa.CheckConstraint("status IN ('OPEN', 'UPHELD', 'DISMISSED')", name="ck_case_flags_status"),
        sa.ForeignKeyConstraint(["case_id"], ["civic_cases.id"]),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "user_id", "kind", name="uq_case_flag"),
    )
    op.create_index("ix_case_flags_case_kind", "case_flags", ["case_id", "kind"], unique=False)
    op.create_index("ix_case_flags_status", "case_flags", ["status"], unique=False)

    # --- 4. evidence_items: malware scan. The server default is what NEW rows get (PENDING); rows that already exist were never scanned -> UNSCANNED.
    with op.batch_alter_table("evidence_items") as batch:
        batch.add_column(sa.Column("scan_status", sa.String(length=16), server_default="PENDING", nullable=False))
        batch.add_column(sa.Column("scan_engine", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("scan_signature", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE evidence_items SET scan_status = 'UNSCANNED'")

    # --- 5. notifications: Expo push delivery state
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("push_status", sa.String(length=16), server_default="NONE", nullable=False))
        batch.add_column(sa.Column("push_attempts", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("pushed_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("push_receipt_id", sa.String(length=128), nullable=True))

    # --- 6. case_embeddings: dimension / model everywhere, pgvector column + indexes only where the extension exists
    with op.batch_alter_table("case_embeddings") as batch:
        batch.add_column(sa.Column("embedding_dim", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("embedding_model", sa.Text(), nullable=True))
    if not _pg():
        return
    if not _vector_available():
        log.warning("0003: the pgvector extension is NOT available on this PostgreSQL server (pg_available_extensions has no 'vector'); added embedding_dim and "
                    "embedding_model only. Vector search is disabled (/api/v1/health/ready reports vector_search=false). Use the image from scripts/dev/db_up.ps1.")
        return
    if not _enable_vector():
        return
    op.execute("ALTER TABLE case_embeddings ADD COLUMN embedding_vec vector")                   # deliberately no dimension, see the module docstring
    for dim in VECTOR_DIMS:
        op.execute(f"CREATE INDEX ix_case_embeddings_vec_{dim} ON case_embeddings USING hnsw ((embedding_vec::vector({dim})) vector_cosine_ops) "
                   f"WHERE (embedding_dim = {dim})")


def downgrade() -> None:
    if _pg():
        for dim in VECTOR_DIMS:
            op.execute(f"DROP INDEX IF EXISTS ix_case_embeddings_vec_{dim}")
        op.execute("ALTER TABLE case_embeddings DROP COLUMN IF EXISTS embedding_vec")
    with op.batch_alter_table("case_embeddings") as batch:
        batch.drop_column("embedding_model")
        batch.drop_column("embedding_dim")
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("push_receipt_id")
        batch.drop_column("pushed_at")
        batch.drop_column("push_attempts")
        batch.drop_column("push_status")
    with op.batch_alter_table("evidence_items") as batch:
        batch.drop_column("scanned_at")
        batch.drop_column("scan_signature")
        batch.drop_column("scan_engine")
        batch.drop_column("scan_status")
    op.drop_index("ix_case_flags_status", table_name="case_flags")
    op.drop_index("ix_case_flags_case_kind", table_name="case_flags")
    op.drop_table("case_flags")
    op.drop_index(op.f("ix_device_tokens_user_id"), table_name="device_tokens")
    op.drop_table("device_tokens")
    op.drop_table("system_settings")
