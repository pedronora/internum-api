from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import get_session
from internum.modules.users.models import User
from internum.modules.users.schemas import (
    FilterPage,
    UserCreate,
    UserList,
    UserRead,
)

router = APIRouter(prefix='/users', tags=['Users'])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserRead)
async def create_user(session: Session, user: UserCreate):
    db_user = await session.scalar(
        select(User).where(
            (User.username == user.username) | (User.email == user.email)
        )
    )

    if db_user:
        if db_user.username == user.username:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Usuário já existente.',
            )
        elif db_user.email == user.email:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='Email já existente.',
            )

    data = user.model_dump()
    db_user = User(**data)

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    return db_user


@router.get('/', response_model=UserList)
async def read_users(
    session: Session, filter_users: Annotated[FilterPage, Query()]
):
    query = await session.scalars(
        select(User)
        .where(User.active)
        .offset(filter_users.offset)
        .limit(filter_users.limit)
    )
    users = query.all()
    return {'users': users}


@router.get('/{user_id}', response_model=UserRead)
async def get_user_by_id(
    user_id: int,
    session: Session,
):
    db_user = await session.scalar(
        select(User).where((User.id == user_id) & (User.active))
    )

    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user_id}).',
        )

    return db_user
