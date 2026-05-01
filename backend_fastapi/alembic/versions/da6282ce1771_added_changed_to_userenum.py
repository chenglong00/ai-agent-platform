"""Added changed to UserEnum

Revision ID: da6282ce1771
Revises: be1d5ce2fda8
Create Date: 2026-03-15 15:48:03.832903

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'da6282ce1771'
down_revision: Union[str, Sequence[str], None] = 'be1d5ce2fda8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename PostgreSQL enum types from authproviderenum/userroleenum to authprovider/userrole to match Python model names."""
    # Create new enum types (names match Python AuthProvider / UserRole).
    op.execute("CREATE TYPE authprovider AS ENUM ('google', 'github', 'microsoft', 'credentials')")
    op.execute("CREATE TYPE userrole AS ENUM ('OWNER', 'ADMIN', 'MEMBER')")
    # Alter columns to use new types (cast via text).
    op.execute(
        "ALTER TABLE auth_identities ALTER COLUMN provider TYPE authprovider USING provider::text::authprovider"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::text::userrole"
    )
    # Drop old enum types.
    op.execute("DROP TYPE authproviderenum")
    op.execute("DROP TYPE userroleenum")


def downgrade() -> None:
    """Revert to authproviderenum / userroleenum."""
    op.execute("CREATE TYPE authproviderenum AS ENUM ('google', 'github', 'microsoft', 'credentials')")
    op.execute("CREATE TYPE userroleenum AS ENUM ('OWNER', 'ADMIN', 'MEMBER')")
    op.execute(
        "ALTER TABLE auth_identities ALTER COLUMN provider TYPE authproviderenum USING provider::text::authproviderenum"
    )
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userroleenum USING role::text::userroleenum"
    )
    op.execute("DROP TYPE authprovider")
    op.execute("DROP TYPE userrole")
