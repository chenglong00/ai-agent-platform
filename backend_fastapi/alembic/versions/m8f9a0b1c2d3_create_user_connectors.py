"""create user_connectors table

Revision ID: m8f9a0b1c2d3
Revises: l7e8f9a0b1c2
Create Date: 2026-06-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m8f9a0b1c2d3"
down_revision: Union[str, Sequence[str], None] = "l7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_connectors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("account_email", sa.String(length=255), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_connected_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "connector_id", name="uq_user_connector"),
    )
    op.create_index(op.f("ix_user_connectors_user_id"), "user_connectors", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_connectors_connector_id"), "user_connectors", ["connector_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_connectors_connector_id"), table_name="user_connectors")
    op.drop_index(op.f("ix_user_connectors_user_id"), table_name="user_connectors")
    op.drop_table("user_connectors")
