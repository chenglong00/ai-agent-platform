"""unique (message_id, position) on message_blocks

Revision ID: h3a4b5c6d7e8
Revises: f1a2b3c4d5e6
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op


revision: str = "h3a4b5c6d7e8"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_message_blocks_message_id_position",
        "message_blocks",
        ["message_id", "position"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_message_blocks_message_id_position",
        "message_blocks",
        type_="unique",
    )
