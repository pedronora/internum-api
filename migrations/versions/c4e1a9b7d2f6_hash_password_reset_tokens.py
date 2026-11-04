"""hash password reset tokens

Revision ID: c4e1a9b7d2f6
Revises: 7f3c9d2a1b45
Create Date: 2026-11-04 02:00:00.000000

"""

import hashlib
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4e1a9b7d2f6'
down_revision: Union[str, Sequence[str], None] = '7f3c9d2a1b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Tokens existentes são convertidos para SHA-256 antes da renomeação, para
    que links de redefinição ainda válidos continuem funcionando.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text('SELECT id, token FROM password_reset_tokens')
    ).fetchall()

    for token_id, token in rows:
        bind.execute(
            sa.text(
                'UPDATE password_reset_tokens SET token = :token_hash '
                'WHERE id = :token_id'
            ),
            {
                'token_hash': hashlib.sha256(
                    token.encode('utf-8')
                ).hexdigest(),
                'token_id': token_id,
            },
        )

    op.alter_column(
        'password_reset_tokens',
        'token',
        new_column_name='token_hash',
        existing_type=sa.String(),
        existing_nullable=False,
    )
    op.alter_column(
        'password_reset_tokens',
        'token_hash',
        type_=sa.String(64),
        existing_type=sa.String(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    O valor original do token não pode ser recuperado a partir do hash; os
    registros existentes são descartados para evitar links inválidos.
    """
    op.execute('DELETE FROM password_reset_tokens')
    op.alter_column(
        'password_reset_tokens',
        'token_hash',
        new_column_name='token',
        existing_type=sa.String(64),
        existing_nullable=False,
    )
    op.alter_column(
        'password_reset_tokens',
        'token',
        type_=sa.String(),
        existing_type=sa.String(64),
        existing_nullable=False,
    )
