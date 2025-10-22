"""remove canceled_at from legal_briefs

Revision ID: 6c56393899c3
Revises: f98572e18b6a
Create Date: 2025-10-22 11:21:50.510971

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c56393899c3'
down_revision: Union[str, Sequence[str], None] = 'f98572e18b6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
