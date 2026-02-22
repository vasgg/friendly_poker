"""initial schema

Revision ID: 20260222_0001
Revises:
Create Date: 2026-02-22 16:05:00
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260222_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    game_status = postgresql.ENUM(
        "ACTIVE",
        "FINISHED",
        "ABORTED",
        name="gamestatus",
        create_type=False,
    )
    game_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("fullname", sa.String(), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("IBAN", sa.String(), nullable=True),
        sa.Column("bank", sa.String(), nullable=True),
        sa.Column("name_surname", sa.String(), nullable=True),
        sa.Column("games_played", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_time_played", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id"),
    )

    op.create_table(
        "games",
        sa.Column("status", game_status, nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("host_id", sa.BigInteger(), nullable=False),
        sa.Column("total_pot", sa.Integer(), nullable=False),
        sa.Column("mvp_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("photo_name", sa.String(), nullable=True),
        sa.Column("photo_id", sa.String(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("ratio", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["mvp_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_games_status", "games", ["status"], unique=False)

    op.create_table(
        "records",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("buy_in", sa.Integer(), nullable=True),
        sa.Column("buy_out", sa.Integer(), nullable=True),
        sa.Column("net_profit", sa.Integer(), nullable=True),
        sa.Column("ROI", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_records_game_user",
        "records",
        ["game_id", "user_id"],
        unique=True,
    )

    op.create_table(
        "debts",
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("creditor_id", sa.BigInteger(), nullable=False),
        sa.Column("debtor_id", sa.BigInteger(), nullable=False),
        sa.Column("debt_message_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["creditor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["debtor_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_debts_game_id", "debts", ["game_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_debts_game_id", table_name="debts")
    op.drop_table("debts")

    op.drop_index("ux_records_game_user", table_name="records")
    op.drop_table("records")

    op.drop_index("ix_games_status", table_name="games")
    op.drop_table("games")

    op.drop_table("users")

    game_status = postgresql.ENUM(
        "ACTIVE",
        "FINISHED",
        "ABORTED",
        name="gamestatus",
        create_type=False,
    )
    game_status.drop(op.get_bind(), checkfirst=True)
