"""add_oauth_tokens_to_auth_identities

Revision ID: 5d8668946cd3
Revises: 65ab11bdd68b
Create Date: 2026-02-17 16:49:19.385314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d8668946cd3'
down_revision: Union[str, Sequence[str], None] = '65ab11bdd68b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add OAuth token columns to auth_identities. Skip altering provider/role to ENUM (init created them as VARCHAR; app works with that)."""
    op.add_column('auth_identities', sa.Column('access_token', sa.String(length=2048), nullable=True))
    op.add_column('auth_identities', sa.Column('refresh_token', sa.String(length=2048), nullable=True))
    op.add_column('auth_identities', sa.Column('token_expires_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove OAuth token columns from auth_identities."""
    op.drop_column('auth_identities', 'token_expires_at')
    op.drop_column('auth_identities', 'refresh_token')
    op.drop_column('auth_identities', 'access_token')
