"""create user_memories table

Revision ID: k6d7e8f9a0b1
Revises: j5c6d7e8f9a0
Create Date: 2026-06-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k6d7e8f9a0b1"
down_revision: Union[str, Sequence[str], None] = "j5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_memories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_memories_user_id"), "user_memories", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_user_memories_category"),
        "user_memories",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_memories_conversation_id"),
        "user_memories",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_memories_conversation_id"), table_name="user_memories")
    op.drop_index(op.f("ix_user_memories_category"), table_name="user_memories")
    op.drop_index(op.f("ix_user_memories_user_id"), table_name="user_memories")
    op.drop_table("user_memories")
