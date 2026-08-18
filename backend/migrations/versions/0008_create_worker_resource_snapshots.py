"""Create immutable worker resource telemetry history.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_resource_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("worker_instance_id", sa.String(), nullable=False),
        sa.Column("host_cpu_percent", sa.Float(), nullable=False),
        sa.Column("host_total_memory_bytes", sa.Integer(), nullable=False),
        sa.Column("host_available_memory_bytes", sa.Integer(), nullable=False),
        sa.Column("process_cpu_percent", sa.Float(), nullable=False),
        sa.Column("process_memory_bytes", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_worker_resource_snapshots_worker_created",
        "worker_resource_snapshots",
        ["worker_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_worker_resource_snapshots_worker_created", table_name="worker_resource_snapshots"
    )
    op.drop_table("worker_resource_snapshots")
