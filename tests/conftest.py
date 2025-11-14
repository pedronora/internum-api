from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock

import factory
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from internum.app import app
from internum.core.database import get_session
from internum.core.models.registry import table_registry
from internum.core.security import get_password_hash
from internum.modules.users.enums import Role, Setor
from internum.modules.users.models import User


class UserFactory(factory.Factory):
    class Meta:
        model = User

    name = factory.Sequence(lambda n: f'User_{n}')
    username = factory.LazyAttribute(lambda obj: obj.name.lower())
    password = factory.Faker(
        'password',
        length=15,
        special_chars=True,
        digits=True,
        upper_case=True,
        lower_case=True,
    )
    email = factory.LazyAttribute(lambda obj: f'{obj.username}@test.com')
    birthday = factory.Faker(
        'date_between_dates',
        date_start=date(1970, 1, 1),
        date_end=date(2005, 12, 31),
    )
    role = Role.USER
    setor = Setor.REGISTRO
    subsetor = 'Análise'


@pytest.fixture
def client(session):
    def get_session_override():
        return session

    with TestClient(app) as client:
        app.dependency_overrides[get_session] = get_session_override
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(scope='session')
def engine():
    with PostgresContainer('postgres:17', driver='psycopg') as postgres:
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
def token(client, user):
    response = client.post(
        'api/v1/auth/token',
        data={'username': user.username, 'password': user.clean_password},
    )
    return response.json()['access_token']


@pytest.fixture
def token_inactive(client, user_inactive):
    response = client.post(
        'api/v1/auth/token',
        data={
            'username': user_inactive.username,
            'password': user_inactive.clean_password,
        },
    )
    return response.json()['access_token']


@pytest.fixture
def token_admin(client, user_admin):
    response = client.post(
        'api/v1/auth/token',
        data={
            'username': user_admin.username,
            'password': user_admin.clean_password,
        },
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
    plain_password = user.password

    user.password = get_password_hash(plain_password)
    user.active = False

    session.add(user)
    await session.commit()
    await session.refresh(user)

    user.clean_password = plain_password
    return user


@pytest_asyncio.fixture
async def user_admin(session):
    user = UserFactory()
    plain_password = user.password

    user.password = get_password_hash(plain_password)
    user.role = 'admin'

    session.add(user)
    await session.commit()
    await session.refresh(user)
    user.clean_password = plain_password

    return user


@pytest_asyncio.fixture
async def other_user(session):
    user = UserFactory()

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@pytest.fixture(autouse=True)
def mock_email_service(monkeypatch):
    from internum.core import email  # noqa: PLC0415

    fake_send = MagicMock()

    monkeypatch.setattr(email.EmailService, 'send_email', fake_send)

    return fake_send
