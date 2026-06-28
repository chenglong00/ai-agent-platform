"""message_blocks: position, JSONB payload, wider block_type

Revision ID: f1a2b3c4d5e6
Revises: e8f9a0b1c2d3
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "message_blocks",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "message_blocks",
        sa.Column("payload", JSONB(), nullable=True),
    )

    # Migrate legacy content strings into structured payloads.
    op.execute(
        """
        UPDATE message_blocks mb
        SET payload = jsonb_build_object('text', mb.content, 'format', 'plain')
        FROM messages m
        WHERE m.id = mb.message_id
        """
    )
    op.execute(
        """
        UPDATE message_blocks mb
        SET payload = jsonb_build_object('text', mb.content, 'format', 'markdown')
        FROM messages m
        WHERE m.id = mb.message_id AND m.role = 'assistant'
        """
    )

    op.alter_column("message_blocks", "payload", nullable=False)
    op.drop_column("message_blocks", "content")

    op.alter_column(
        "message_blocks",
        "block_type",
        existing_type=sa.String(length=5),
        type_=sa.String(length=20),
        existing_nullable=False,
    )

    # Backfill position from insertion order per message.
    op.execute(
        """
        UPDATE message_blocks mb
        SET position = ranked.idx
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY message_id ORDER BY id
            ) - 1 AS idx
            FROM message_blocks
        ) ranked
        WHERE mb.id = ranked.id
        """
    )
    op.alter_column("message_blocks", "position", server_default=None)


def downgrade() -> None:
    op.add_column(
        "message_blocks",
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE message_blocks
        SET content = COALESCE(payload->>'text', payload::text)
        """
    )
    op.alter_column("message_blocks", "content", nullable=False)

    op.alter_column(
        "message_blocks",
        "block_type",
        existing_type=sa.String(length=20),
        type_=sa.String(length=5),
        existing_nullable=False,
    )
    op.drop_column("message_blocks", "payload")
    op.drop_column("message_blocks", "position")
