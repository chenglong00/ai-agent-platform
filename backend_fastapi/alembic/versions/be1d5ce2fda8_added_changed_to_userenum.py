"""Added changed to UserEnum

Revision ID: be1d5ce2fda8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-15 15:41:45.539583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'be1d5ce2fda8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: create PostgreSQL enum types, then alter columns from VARCHAR to enum."""
    # Create enum types first (PostgreSQL requires this before using them in ALTER COLUMN).
    op.execute("CREATE TYPE authproviderenum AS ENUM ('google', 'github', 'microsoft', 'credentials')")
    op.execute("CREATE TYPE userroleenum AS ENUM ('OWNER', 'ADMIN', 'MEMBER')")
    # Alter columns with USING to cast existing varchar values to the new enum types.
    op.execute(
        "ALTER TABLE auth_identities ALTER COLUMN provider TYPE authproviderenum USING provider::authproviderenum"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userroleenum USING role::userroleenum"
    )


def downgrade() -> None:
    """Downgrade schema: alter columns back to VARCHAR, then drop enum types."""
    op.execute("ALTER TABLE auth_identities ALTER COLUMN provider TYPE VARCHAR(32) USING provider::text")
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(32) USING role::text")
    op.execute("DROP TYPE authproviderenum")
    op.execute("DROP TYPE userroleenum")
