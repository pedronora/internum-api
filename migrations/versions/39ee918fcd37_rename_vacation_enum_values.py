"""rename vacation enum values

Revision ID: 39ee918fcd37
Revises: a911d5bbe8d1
Create Date: 2026-08-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '39ee918fcd37'
down_revision: Union[str, Sequence[str], None] = 'a911d5bbe8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Renomeia valores do enum de status do período aquisitivo
    op.execute(
        "ALTER TYPE vacation_accrual_status_enum "
        "RENAME VALUE 'ACTIVE' TO 'ACQUISITIVE'"
    )
    # Renomeia valores do enum de tipo de período de férias
    op.execute(
        "ALTER TYPE vacation_period_type_enum "
        "RENAME VALUE 'FULL' TO 'MAIN'"
    )
    op.execute(
        "ALTER TYPE vacation_period_type_enum "
        "RENAME VALUE 'PROPORTIONAL' TO 'COMPLEMENTARY'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "ALTER TYPE vacation_period_type_enum "
        "RENAME VALUE 'COMPLEMENTARY' TO 'PROPORTIONAL'"
    )
    op.execute(
        "ALTER TYPE vacation_period_type_enum "
        "RENAME VALUE 'MAIN' TO 'FULL'"
    )
    op.execute(
        "ALTER TYPE vacation_accrual_status_enum "
        "RENAME VALUE 'ACQUISITIVE' TO 'ACTIVE'"
    )