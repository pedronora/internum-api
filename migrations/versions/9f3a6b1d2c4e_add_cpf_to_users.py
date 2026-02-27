"""Add CPF to users

Revision ID: 9f3a6b1d2c4e
Revises: 504a0de55569
Create Date: 2026-02-27 09:15:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9f3a6b1d2c4e'
down_revision: Union[str, Sequence[str], None] = '504a0de55569'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('cpf', sa.String(length=11), nullable=True),
    )
    op.execute("UPDATE users SET cpf = '12345678909' WHERE cpf IS NULL")
    op.alter_column(
        'users',
        'cpf',
        existing_type=sa.String(length=11),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'cpf')
