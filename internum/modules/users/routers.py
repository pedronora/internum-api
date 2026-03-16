import math
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import get_session
from internum.core.permissions import (
    CurrentUser,
    VerifyAdminCoord,
    VerifySelfAdmin,
    VerifySelfAdminCoord,
)
from internum.core.security import get_password_hash, verify_password
from internum.modules.users.models import User
from internum.modules.users.schemas import (
    Message,
    PageMeta,
    PaginatedUserList,
    UserChangePassword,
    UserCreate,
    UserQueryParams,
    UserRead,
    UserUpdate,
)

router = APIRouter(prefix='/users', tags=['Users'])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserRead)
async def create_user(
    session: Session,
    user: UserCreate,
    current_user: VerifyAdminCoord,
):
    db_user = await session.scalar(
        select(User).where(
            (User.username == user.username)
            | (User.email == user.email)
            | (User.cpf == user.cpf)
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
        elif db_user.cpf == user.cpf:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail='CPF já existente.',
            )

    data = user.model_dump()
    data['password'] = get_password_hash(data['password'])

    if data['role'] == 'admin' and current_user.role != 'admin':
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: Somente administradores podem '
            'atribuir o perfil de administrador.',
        )

    db_user = User(**data)

    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)

    return db_user


@router.get('/', response_model=PaginatedUserList)
async def read_users(
    session: Session,
    params: Annotated[UserQueryParams, Depends()],
    current_user: VerifyAdminCoord,
):
    limit = max(1, params.limit)
    offset = max(0, params.offset)
    search = params.search

    filters = [User.active]

    if search:
        search_pattern = f'%{search}%'

        search_filters = or_(
            User.name.ilike(search_pattern),
            User.username.ilike(search_pattern),
            User.email.ilike(search_pattern),
        )

        filters.append(search_filters)

    total: int = (
        await session.scalar(
            select(func.count()).select_from(User).where(*filters)
        )
        | 0
    )

    query = await session.scalars(
        select(User)
        .where(*filters)
        .order_by(User.name)
        .offset(offset)
        .limit(limit)
    )
    users = query.all()

    total_pages = math.ceil(total / limit) if limit > 0 else 1
    page = (offset // limit) + 1 if limit > 0 else 1
    has_next = (offset + limit) < total
    has_prev = offset > 0

    meta = PageMeta(
        total=total,
        page=page,
        size=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
        offset=offset,
    )

    return {'meta': meta, 'users': users}


@router.get('/me', response_model=UserRead)
async def get_current_user_data(session: Session, current_user: CurrentUser):
    return current_user


@router.get('/{user_id}', response_model=UserRead)
async def get_user_by_id(
    user_id: int,
    session: Session,
    current_user: VerifySelfAdminCoord,
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


@router.put('/{user_id}', response_model=UserRead, status_code=HTTPStatus.OK)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    session: Session,
    current_user: VerifySelfAdminCoord,
):
    db_user = await session.scalar(
        select(User).where((User.id == user_id) & (User.active))
    )

    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user_id}).',
        )

    update_data = user_data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None and hasattr(db_user, field):
            sensitive_fields = {
                'role',
                'setor',
                'subsetor',
                'active',
                'hiring_date',
                'termination_date',
            }

            if field in sensitive_fields and current_user.role not in {
                'admin',
                'coord',
            }:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail='Acesso negado: sem permissão para alterar campos '
                    'administrativos.',
                )

            if (
                field == 'role'
                and value == 'admin'
                and current_user.role != 'admin'
            ):
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail='Acesso negado: Somente administradores podem '
                    'atribuir o perfil de administrador.',
                )

            setattr(db_user, field, value)

    if update_data.get('active') is True:
        db_user.termination_date = None

    try:
        await session.commit()
        await session.refresh(db_user)
        return db_user

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Username, Email ou CPF já existem.',
        )
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f'Erro interno ao atualizar usuário: {str(e)}',
        )


@router.delete('/{user_id}', status_code=HTTPStatus.NO_CONTENT)
async def deactivate_user(
    user_id: int,
    session: Session,
    current_user: VerifyAdminCoord,
):
    db_user = await session.scalar(select(User).where(User.id == user_id))

    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user_id}).',
        )

    if not db_user.active:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f'Usuário com id ({user_id}) já está inativo.',
        )

    db_user.active = False
    await session.commit()


@router.post(
    '/{user_id}/change-password',
    response_model=Message,
    status_code=HTTPStatus.OK,
)
async def change_password(
    user_id: int,
    passwords: UserChangePassword,
    session: Session,
    current_user: VerifySelfAdmin,
):
    db_user = await session.scalar(select(User).where(User.id == user_id))

    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user_id}).',
        )

    if not verify_password(passwords.old_password, db_user.password):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Senha antiga incorreta.',
        )

    if verify_password(passwords.new_password, db_user.password):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Senha nova igual à atual.',
        )

    db_user.password = get_password_hash(passwords.new_password)
    await session.commit()

    return {'message': 'Senha alterada com sucesso'}
