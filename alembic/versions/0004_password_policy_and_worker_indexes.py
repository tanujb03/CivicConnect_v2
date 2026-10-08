"""users.must_change_password / password_changed_at; indexes for the push worker, scan worker and flag review

Revision ID: 0004
Revises: 0003

Works on PostgreSQL and SQLite (batch operations), reversible. The only revision of docs/BACKEND_BUILD_PLAN.md: later work packages add no schema.

* ``users.must_change_password`` (NOT NULL, default false) and ``users.password_changed_at`` (NULL): WP2 forces a new password after an admin created or reset an account.
  Existing rows get ``false``: nobody is locked out by the upgrade.
* ``ix_device_tokens_user_active (user_id, revoked_at)``: the active tokens of a user (push sender, device list).
* ``ix_notif_push_status (push_status, created_at)``: the push worker scans PENDING / FAILED rows oldest first.
* ``ix_evidence_scan_status (scan_status)``: the scan worker and the quarantine gate.
* ``ix_case_flags_case_status (case_id, status)``: open flags of a case. The unique ``(case_id, user_id, kind)`` already exists (``uq_case_flag``, migration 0003).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_device_tokens_user_active", "device_tokens", ["user_id", "revoked_at"], unique=False)
    op.create_index("ix_notif_push_status", "notifications", ["push_status", "created_at"], unique=False)
    op.create_index("ix_evidence_scan_status", "evidence_items", ["scan_status"], unique=False)
    op.create_index("ix_case_flags_case_status", "case_flags", ["case_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_case_flags_case_status", table_name="case_flags")
    op.drop_index("ix_evidence_scan_status", table_name="evidence_items")
    op.drop_index("ix_notif_push_status", table_name="notifications")
    op.drop_index("ix_device_tokens_user_active", table_name="device_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_changed_at")
        batch.drop_column("must_change_password")
