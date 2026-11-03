"""add session started at to refresh tokens

Revision ID: 348e34b4a4e4
Revises: b7d043bca441
Create Date: 2026-11-03 06:58:15.418859

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '348e34b4a4e4'
down_revision: Union[str, Sequence[str], None] = 'b7d043bca441'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'refresh_tokens',
        sa.Column(
            'session_started_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute('UPDATE refresh_tokens SET session_started_at = created_at')
    op.alter_column('refresh_tokens', 'session_started_at', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('refresh_tokens', 'session_started_at')
