"""Add unique constraint to users.cpf

Revision ID: 6e2a9c4b1d7f
Revises: c7b4d1e8f2a9
Create Date: 2026-02-27 12:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6e2a9c4b1d7f'
down_revision: Union[str, Sequence[str], None] = 'c7b4d1e8f2a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    duplicate_cpfs = connection.execute(
        sa.text(
            """
            SELECT cpf
            FROM users
            GROUP BY cpf
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    if duplicate_cpfs:
        raise RuntimeError(
            'Não foi possível criar unicidade de CPF: existem CPFs '
            'duplicados na tabela users.'
        )

    op.create_unique_constraint('uq_users_cpf', 'users', ['cpf'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_users_cpf', 'users', type_='unique')
