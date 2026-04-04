"""shared next-game settings

Revision ID: 20260404_0003
Revises: 20260222_0002
Create Date: 2026-04-04 12:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260404_0003"
down_revision = "20260222_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "games",
        sa.Column(
            "send_yearly_stats_on_finish",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )

    op.create_table(
        "next_game_settings",
        sa.Column("ratio", sa.Integer(), server_default="1", nullable=False),
        sa.Column("yearly_stats", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("updated_by_admin_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_by_admin_name", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_next_game_settings_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO next_game_settings (
                id,
                created_at,
                ratio,
                yearly_stats,
                version,
                updated_by_admin_id,
                updated_by_admin_name,
                updated_at
            )
            VALUES (1, CURRENT_TIMESTAMP, 1, FALSE, 1, NULL, NULL, NULL)
            """
        )
    )


def downgrade() -> None:
    op.drop_table("next_game_settings")
    op.drop_column("games", "send_yearly_stats_on_finish")
