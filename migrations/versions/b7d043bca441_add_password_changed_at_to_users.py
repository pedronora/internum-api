"""add password changed at to users

Revision ID: b7d043bca441
Revises: 11ff6501b3c2
Create Date: 2026-11-03 06:20:29.441175

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7d043bca441'
down_revision: Union[str, Sequence[str], None] = '11ff6501b3c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column(
            'password_changed_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute('UPDATE users SET password_changed_at = now()')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'password_changed_at')
