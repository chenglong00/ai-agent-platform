"""encrypted_oauth_token_columns

Revision ID: a1b2c3d4e5f6
Revises: 5d8668946cd3
Create Date: 2026-02-17

Alter access_token and refresh_token to TEXT so encrypted values (Fernet) fit.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "5d8668946cd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "auth_identities",
        "access_token",
        existing_type=sa.String(length=2048),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "auth_identities",
        "refresh_token",
        existing_type=sa.String(length=2048),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "auth_identities",
        "access_token",
        existing_type=sa.Text(),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )
    op.alter_column(
        "auth_identities",
        "refresh_token",
        existing_type=sa.Text(),
        type_=sa.String(length=2048),
        existing_nullable=True,
    )
