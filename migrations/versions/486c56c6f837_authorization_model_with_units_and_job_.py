"""authorization model with units and job roles

Revision ID: 486c56c6f837
Revises: b061be051fe4
Create Date: 2026-10-31 13:56:29.176342

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '486c56c6f837'
down_revision: Union[str, Sequence[str], None] = 'b061be051fe4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Substitui setor/role por unidade e user_roles (perfis de cargo)."""
    op.execute(
        "CREATE TYPE unidade_enum AS ENUM ('DIRECAO', 'REGISTRO', 'GESTAO')"
    )
    op.add_column(
        'users',
        sa.Column(
            'unidade',
            postgresql.ENUM(
                'DIRECAO',
                'REGISTRO',
                'GESTAO',
                name='unidade_enum',
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE users
        SET unidade = CASE
            WHEN setor = 'OFICIAL' THEN 'DIRECAO'::unidade_enum
            WHEN setor = 'ADMINISTRATIVO' THEN 'GESTAO'::unidade_enum
            ELSE 'REGISTRO'::unidade_enum
        END
        """
    )
    op.alter_column('users', 'unidade', nullable=False)

    op.add_column(
        'users', sa.Column('subunidade', sa.String(length=80), nullable=True)
    )
    op.execute('UPDATE users SET subunidade = subsetor')
    op.drop_column('users', 'subsetor')

    op.execute(
        """
        CREATE TABLE _legacy_user_roles AS
        SELECT id AS user_id, role::text AS old_role FROM users
        """
    )
    op.drop_column('users', 'role')
    op.execute('DROP TYPE role_enum')
    op.execute(
        """
        CREATE TYPE role_enum AS ENUM (
            'ADMIN',
            'OFICIAL',
            'SUBOFICIAL',
            'COORD_REGISTRO',
            'COORD_GESTAO',
            'GESTOR_PESSOAS',
            'COLABORADOR_REGISTRO',
            'COLABORADOR_GESTAO'
        )
        """
    )

    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column(
            'role',
            postgresql.ENUM(
                'ADMIN',
                'OFICIAL',
                'SUBOFICIAL',
                'COORD_REGISTRO',
                'COORD_GESTAO',
                'GESTOR_PESSOAS',
                'COLABORADOR_REGISTRO',
                'COLABORADOR_GESTAO',
                name='role_enum',
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column('granted_by_id', sa.Integer(), nullable=True),
        sa.Column(
            'granted_at',
            sa.DateTime(timezone=True),
            server_default=sa.text("timezone('UTC', now())"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['granted_by_id'], ['users.id'], ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role', name='uq_user_roles_user_role'),
    )

    op.execute(
        """
        INSERT INTO user_roles (user_id, role)
        SELECT user_id,
               CASE old_role
                   WHEN 'ADMIN' THEN 'ADMIN'::role_enum
                   WHEN 'COORD' THEN 'COORD_REGISTRO'::role_enum
                   ELSE 'COLABORADOR_REGISTRO'::role_enum
               END
        FROM _legacy_user_roles
        """
    )
    op.execute('DROP TABLE _legacy_user_roles')

    op.drop_column('users', 'setor')
    op.execute('DROP TYPE setor_enum')


def downgrade() -> None:
    """Restaura setor/role a partir de unidade/user_roles."""
    op.execute(
        "CREATE TYPE setor_enum AS ENUM ('REGISTRO', 'ADMINISTRATIVO', 'OFICIAL')"
    )
    op.add_column(
        'users',
        sa.Column(
            'setor',
            postgresql.ENUM(
                'REGISTRO',
                'ADMINISTRATIVO',
                'OFICIAL',
                name='setor_enum',
                create_type=False,
            ),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE users
        SET setor = CASE
            WHEN unidade = 'DIRECAO' THEN 'OFICIAL'::setor_enum
            WHEN unidade = 'GESTAO' THEN 'ADMINISTRATIVO'::setor_enum
            ELSE 'REGISTRO'::setor_enum
        END
        """
    )
    op.alter_column('users', 'setor', nullable=False)

    op.add_column(
        'users', sa.Column('subsetor', sa.String(), nullable=True)
    )
    op.execute("UPDATE users SET subsetor = COALESCE(subunidade, '')")
    op.alter_column('users', 'subsetor', nullable=False)

    op.execute(
        """
        CREATE TABLE _legacy_user_roles AS
        SELECT DISTINCT ON (user_id)
            user_id,
            CASE
                WHEN role = 'ADMIN' THEN 'ADMIN'
                WHEN role IN ('COORD_REGISTRO', 'COORD_GESTAO') THEN 'COORD'
                ELSE 'USER'
            END AS old_role
        FROM user_roles
        ORDER BY user_id,
            CASE
                WHEN role = 'ADMIN' THEN 0
                WHEN role IN ('COORD_REGISTRO', 'COORD_GESTAO') THEN 1
                ELSE 2
            END
        """
    )
    op.drop_table('user_roles')
    op.execute('DROP TYPE role_enum')
    op.execute("CREATE TYPE role_enum AS ENUM ('ADMIN', 'COORD', 'USER')")

    op.add_column(
        'users',
        sa.Column(
            'role',
            postgresql.ENUM(
                'ADMIN', 'COORD', 'USER', name='role_enum', create_type=False
            ),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE users
        SET role = COALESCE(
            (
                SELECT old_role::role_enum
                FROM _legacy_user_roles legacy
                WHERE legacy.user_id = users.id
            ),
            'USER'::role_enum
        )
        """
    )
    op.alter_column('users', 'role', nullable=False)
    op.execute('DROP TABLE _legacy_user_roles')

    op.drop_column('users', 'subunidade')
    op.drop_column('users', 'unidade')
    op.execute('DROP TYPE unidade_enum')
