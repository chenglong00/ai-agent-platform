"""create user_subagents table

Revision ID: o0a1b2c3d4e5
Revises: n9a0b1c2d3e4
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "o0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "n9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_subagents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("agent_url", sa.String(length=2048), nullable=False),
        sa.Column("agent_card", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "agent_url", name="uq_user_subagent_url"),
    )
    op.create_index(op.f("ix_user_subagents_user_id"), "user_subagents", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_subagents_user_id"), table_name="user_subagents")
    op.drop_table("user_subagents")
