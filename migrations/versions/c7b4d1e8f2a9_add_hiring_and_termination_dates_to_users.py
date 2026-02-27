"""Add hiring and termination dates to users

Revision ID: c7b4d1e8f2a9
Revises: 9f3a6b1d2c4e
Create Date: 2026-02-27 10:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c7b4d1e8f2a9'
down_revision: Union[str, Sequence[str], None] = '9f3a6b1d2c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('hiring_date', sa.Date(), nullable=True))
    op.add_column(
        'users', sa.Column('termination_date', sa.Date(), nullable=True)
    )

    op.execute(
        """
        UPDATE users
        SET hiring_date = COALESCE(hiring_date, CAST(created_at AS DATE), CURRENT_DATE)
        WHERE hiring_date IS NULL
        """
    )

    op.alter_column('users', 'hiring_date', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'termination_date')
    op.drop_column('users', 'hiring_date')
