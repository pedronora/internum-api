from contextlib import contextmanager
from datetime import datetime

import factory
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from internum.app import app
from internum.core.database import get_session
from internum.core.security import get_password_hash
from internum.modules.users.enums import Role, Setor
from internum.modules.users.models import User, table_registry


class UserFactory(factory.Factory):
    class Meta:
        model = User

    name = factory.Sequence(lambda n: f'User_{n}')
    username = factory.LazyAttribute(lambda obj: obj.name.lower())
    password = factory.LazyAttribute(lambda obj: f'{obj.username}@example.com')
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    role = Role.USER
    setor = Setor.REGISTRO
    subsetor = 'Análise'


@pytest.fixture(scope='session')
def engine():
    with PostgresContainer('postgres:16', driver='psycopg') as postgres:
        _engine = create_async_engine(postgres.get_connection_url())
        yield _engine


@pytest_asyncio.fixture
async def session(engine):
    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.create_all)

    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(table_registry.metadata.drop_all)


@pytest.fixture
def client(session):
    def get_session_override():
        return session

    with TestClient(app) as client:
        app.dependency_overrides[get_session] = get_session_override
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def token(client, user):
    response = client.post(
        'api/v1/auth/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    return response.json()['access_token']


@contextmanager
def _mock_db_time(*, model, time=datetime(2025, 5, 21)):
    def fake_time_hook(mapper, connection, target):
        if hasattr(target, 'created_at'):
            target.created_at = time
        if hasattr(target, 'updated_at'):
            target.updated_at = time

    event.listen(model, 'before_insert', fake_time_hook)
    event.listen(model, 'before_update', fake_time_hook)

    yield time

    event.remove(model, 'before_insert', fake_time_hook)
    event.listen(model, 'before_update', fake_time_hook)


@pytest.fixture
def mock_db_time():
    return _mock_db_time


@pytest_asyncio.fixture
async def user(session):
    user = UserFactory()
    plain_password = user.password

    user.password = get_password_hash(plain_password)

    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = plain_password

    return user


@pytest_asyncio.fixture
async def user_inactive(session):
    user = UserFactory()

    user.active = False

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@pytest_asyncio.fixture
async def another_user(session):
    user = UserFactory()

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user
