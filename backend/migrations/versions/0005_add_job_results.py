"""Store runtime results and safe failure messages on jobs.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("result_payload", sa.JSON(), nullable=True))
    op.add_column("jobs", sa.Column("error_message", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "error_message")
    op.drop_column("jobs", "result_payload")
