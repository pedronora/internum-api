"""single oficial role

Revision ID: 7f3c9d2a1b45
Revises: 348e34b4a4e4
Create Date: 2026-11-03 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7f3c9d2a1b45'
down_revision: Union[str, Sequence[str], None] = '348e34b4a4e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ROLE_VALUES = (
    'OFICIAL',
    'SUBOFICIAL',
    'COORD_REGISTRO',
    'COORD_GESTAO',
    'GESTOR_PESSOAS',
    'COLABORADOR_REGISTRO',
    'COLABORADOR_GESTAO',
)


def _create_role_enum(values: Sequence[str]) -> None:
    formatted = ',\n            '.join(f"'{value}'" for value in values)
    op.execute(
        f"""
        CREATE TYPE role_enum AS ENUM (
            {formatted}
        )
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    # O perfil `admin` foi eliminado. O banco pode ser recriado pelo seed,
    # então os vínculos antigos são descartados em vez de migrados.
    op.execute("DELETE FROM user_roles WHERE role = 'ADMIN'")

    # A organização tem um único oficial. Vínculos excedentes (criados pelo
    # seed aleatório antigo) são removidos antes de criar o índice único.
    op.execute(
        """
        DELETE FROM user_roles
        WHERE role = 'OFICIAL'
          AND id NOT IN (
              SELECT MIN(id) FROM user_roles WHERE role = 'OFICIAL'
          )
        """
    )

    op.execute('ALTER TYPE role_enum RENAME TO role_enum_old')
    _create_role_enum(ROLE_VALUES)
    op.execute(
        """
        ALTER TABLE user_roles
        ALTER COLUMN role TYPE role_enum
        USING role::text::role_enum
        """
    )
    op.execute('DROP TYPE role_enum_old')

    op.execute(
        """
        CREATE UNIQUE INDEX uq_user_roles_single_oficial
        ON user_roles (role)
        WHERE role = 'OFICIAL'
        """
    )


def downgrade() -> None:
    """Downgrade schema.

    A remoção do perfil `admin` é irreversível: o tipo é recriado com o valor,
    mas os vínculos antigos não são restaurados.
    """
    op.execute('DROP INDEX uq_user_roles_single_oficial')
    op.execute('ALTER TYPE role_enum RENAME TO role_enum_old')
    _create_role_enum(('ADMIN', *ROLE_VALUES))
    op.execute(
        """
        ALTER TABLE user_roles
        ALTER COLUMN role TYPE role_enum
        USING role::text::role_enum
        """
    )
    op.execute('DROP TYPE role_enum_old')
