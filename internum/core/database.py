from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from internum.core.settings import Settings

engine = create_async_engine(
    Settings().DATABASE_URL, connect_args={'options': '-c timezone=UTC'}
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_session():  # pragma: no cover
    async with async_session_maker() as session:
        yield session
