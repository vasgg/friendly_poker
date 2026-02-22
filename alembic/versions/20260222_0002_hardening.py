"""schema hardening and ROI precision

Revision ID: 20260222_0002
Revises: 20260222_0001
Create Date: 2026-02-22 16:12:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260222_0002"
down_revision = "20260222_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "records",
        "ROI",
        existing_type=sa.Integer(),
        type_=sa.Numeric(7, 2),
        existing_nullable=True,
        postgresql_using='"ROI"::numeric(7,2)',
    )

    op.create_index("ix_debts_creditor_id", "debts", ["creditor_id"], unique=False)
    op.create_index("ix_debts_debtor_id", "debts", ["debtor_id"], unique=False)
    op.create_index(
        "ux_games_single_active",
        "games",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )


def downgrade() -> None:
    op.drop_index("ux_games_single_active", table_name="games")
    op.drop_index("ix_debts_debtor_id", table_name="debts")
    op.drop_index("ix_debts_creditor_id", table_name="debts")

    op.alter_column(
        "records",
        "ROI",
        existing_type=sa.Numeric(7, 2),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using='ROUND("ROI")::integer',
    )
