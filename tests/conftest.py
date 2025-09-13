from contextlib import contextmanager
from datetime import datetime

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from internum.app import app
from internum.core.database import get_session
from internum.core.settings import Settings
from internum.modules.users.models import table_registry


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(Settings().DATABASE_URL)

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
