import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from internum.core.security import get_password_hash
from internum.modules.users.enums import Role
from internum.modules.users.models import UserRole
from internum.scripts.seed_oficial import create_oficial
from tests.conftest import UserFactory


@pytest.mark.asyncio
async def test_seed_oficial_is_idempotent(session):
    await create_oficial(session)
    await create_oficial(session)

    total = await session.scalar(
        select(func.count())
        .select_from(UserRole)
        .where(UserRole.role == Role.OFICIAL)
    )

    assert total == 1


@pytest.mark.asyncio
async def test_database_rejects_second_oficial(session, user_oficial):
    other = UserFactory()
    other.password = get_password_hash(other.password)

    session.add(other)
    await session.flush()
    session.add(UserRole(user_id=other.id, role=Role.OFICIAL))

    with pytest.raises(IntegrityError):
        await session.commit()

    await session.rollback()
