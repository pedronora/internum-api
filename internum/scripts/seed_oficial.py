import asyncio
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import get_session
from internum.core.security import get_password_hash
from internum.core.settings import Settings
from internum.modules.users.enums import Role, Unidade
from internum.modules.users.models import User, UserRole

settings = Settings()
Session = Annotated[AsyncSession, Depends(get_session)]


async def create_oficial(session: Session) -> None:
    """Cria a conta única do oficial, se ela ainda não existir.

    O seed é idempotente: a organização tem no máximo um oficial e a conta é
    criada apenas por este script, nunca pela API.
    """
    existing_oficial = await session.scalar(
        select(UserRole).where(UserRole.role == Role.OFICIAL)
    )

    if existing_oficial:
        print('Oficial já existe. Nada a fazer.')
        return

    existing_user = await session.scalar(
        select(User).where(User.username == settings.ADMIN_USERNAME)
    )

    if existing_user:
        session.add(
            UserRole(
                user_id=existing_user.id,
                role=Role.OFICIAL,
                granted_by_id=existing_user.id,
            )
        )
        await session.commit()
        print(
            f'Perfil de oficial atribuído ao usuário existente '
            f'{existing_user.name}.'
        )
        return

    oficial = User(
        name=settings.ADMIN_NAME,
        username=settings.ADMIN_USERNAME,
        email=settings.ADMIN_EMAIL,
        cpf=settings.ADMIN_CPF,
        birthday=settings.ADMIN_BIRTHDAY,
        password=get_password_hash(settings.ADMIN_PASSWORD),
        unidade=Unidade.GESTAO,
        hiring_date=settings.ADMIN_HIRING_DATE or settings.ADMIN_BIRTHDAY,
    )

    session.add(oficial)
    await session.flush()
    session.add(
        UserRole(
            user_id=oficial.id,
            role=Role.OFICIAL,
            granted_by_id=oficial.id,
        )
    )
    await session.commit()

    print(f'Usuário {oficial.name} criado com sucesso como oficial!')


if __name__ == '__main__':

    async def main():
        session_generator = get_session()
        try:
            session = await anext(session_generator)
            await create_oficial(session)
        finally:
            try:
                await anext(session_generator)
            except StopAsyncIteration:
                pass

    asyncio.run(main())
