"""Create durable model-residency snapshots.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_residencies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_revision", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("worker_instance_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("active_execution_count", sa.Integer(), nullable=False),
        sa.Column("measured_memory_bytes", sa.Integer(), nullable=True),
        sa.Column("loaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_model_residencies_worker",
        "model_residencies",
        ["worker_id", "worker_instance_id"],
    )
    op.create_index("ix_model_residencies_model", "model_residencies", ["model_id"])


def downgrade() -> None:
    op.drop_index("ix_model_residencies_model", table_name="model_residencies")
    op.drop_index("ix_model_residencies_worker", table_name="model_residencies")
    op.drop_table("model_residencies")
