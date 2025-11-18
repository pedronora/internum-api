import asyncio
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import get_session
from internum.core.security import get_password_hash
from internum.core.settings import Settings
from internum.modules.users.enums import Role, Setor
from internum.modules.users.models import User

settings = Settings()
Session = Annotated[AsyncSession, Depends(get_session)]


async def create_admin(session: Session):
    admin = User(
        name=settings.ADMIN_NAME,
        username=settings.ADMIN_USERNAME,
        email=settings.ADMIN_EMAIL,
        birthday=settings.ADMIN_BIRTHDAY,
        password=get_password_hash(settings.ADMIN_PASSWORD),
        role=Role.ADMIN,
        setor=Setor.ADMINISTRATIVO,
        subsetor='Apoio',
    )

    session.add(admin)
    await session.commit()
    await session.refresh(admin)

    print(f'Usuário {admin.name} criado com sucesso!')


if __name__ == '__main__':

    async def main():
        session_generator = get_session()
        try:
            session = await anext(session_generator)
            await create_admin(session)
        finally:
            try:
                await anext(session_generator)
            except StopAsyncIteration:
                pass

    asyncio.run(main())
