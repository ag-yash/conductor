"""Create durable runtime benchmark summaries.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "benchmark_summaries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column("model_revision", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=False),
        sa.Column("worker_instance_id", sa.String(), nullable=False),
        sa.Column("task", sa.String(), nullable=False),
        sa.Column("warmup_iterations", sa.Integer(), nullable=False),
        sa.Column("measurement_iterations", sa.Integer(), nullable=False),
        sa.Column("total_wall_time_ms", sa.Float(), nullable=False),
        sa.Column("mean_wall_time_ms", sa.Float(), nullable=False),
        sa.Column("min_wall_time_ms", sa.Float(), nullable=False),
        sa.Column("max_wall_time_ms", sa.Float(), nullable=False),
        sa.Column("mean_runtime_metrics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_benchmark_summaries_worker_created",
        "benchmark_summaries",
        ["worker_id", "created_at"],
    )
    op.create_index(
        "ix_benchmark_summaries_model_created",
        "benchmark_summaries",
        ["model_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_benchmark_summaries_model_created", table_name="benchmark_summaries")
    op.drop_index("ix_benchmark_summaries_worker_created", table_name="benchmark_summaries")
    op.drop_table("benchmark_summaries")
