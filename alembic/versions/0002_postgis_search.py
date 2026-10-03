"""PostGIS geometry, GiST index and full-text search (PostgreSQL only; a no-op elsewhere)

Revision ID: 0002
Revises: 0001
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _pg():
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    # design §33 / §54: a generated geography point (metres, ST_DWithin) kept in sync with latitude/longitude by the database itself
    op.execute("ALTER TABLE civic_cases ADD COLUMN geog geography(Point, 4326) GENERATED ALWAYS AS "
               "(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED")
    op.execute("CREATE INDEX ix_civic_cases_geog ON civic_cases USING GIST (geog)")
    op.execute("ALTER TABLE incidents ADD COLUMN geog geography(Point, 4326) GENERATED ALWAYS AS "
               "(CASE WHEN center_lat IS NULL OR center_lon IS NULL THEN NULL "
               "ELSE ST_SetSRID(ST_MakePoint(center_lon, center_lat), 4326)::geography END) STORED")
    # full-text search over title + description + case number (the 'simple' config keeps Hindi / Marathi tokens intact)
    op.execute("CREATE INDEX ix_civic_cases_fts ON civic_cases USING GIN "
               "(to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || case_number))")


def downgrade() -> None:
    if not _pg():
        return
    op.execute("DROP INDEX IF EXISTS ix_civic_cases_fts")
    op.execute("ALTER TABLE incidents DROP COLUMN IF EXISTS geog")
    op.execute("DROP INDEX IF EXISTS ix_civic_cases_geog")
    op.execute("ALTER TABLE civic_cases DROP COLUMN IF EXISTS geog")
