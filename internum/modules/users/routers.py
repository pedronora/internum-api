from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import get_session
from internum.modules.users.models import User
from internum.modules.users.schemas import FilterPage, UserList

router = APIRouter(prefix='/users', tags=['Users'])

Session = Annotated[AsyncSession, Depends(get_session)]


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
