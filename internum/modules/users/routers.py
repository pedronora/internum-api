import math
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.authorization import (
    Permission,
    can_assign_role,
    has_permission,
    permissions_for_roles,
)
from internum.core.database import get_session
from internum.core.permissions import DENIED, CurrentUser, require_permission
from internum.core.security import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from internum.core.settings import Settings
from internum.modules.auth.services import (
    delete_user_tokens,
    refresh_token_jti,
)
from internum.modules.users.enums import Role
from internum.modules.users.models import User, UserRole
from internum.modules.users.schemas import (
    ChangePasswordResponse,
    PageMeta,
    PaginatedUserDirectory,
    PaginatedUserList,
    UserChangePassword,
    UserCreate,
    UserPublic,
    UserQueryParams,
    UserRead,
    UserSelf,
    UserUpdate,
)

router = APIRouter(prefix='/users', tags=['Users'])
settings = Settings()

Session = Annotated[AsyncSession, Depends(get_session)]

CanCreateUser = Annotated[
    UserRead, Depends(require_permission(Permission.USERS_CREATE))
]
CanReadSensitive = Annotated[
    UserRead, Depends(require_permission(Permission.USERS_READ_SENSITIVE))
]
CanReadDirectory = Annotated[
    UserRead, Depends(require_permission(Permission.USERS_READ))
]
CanEditEmployment = Annotated[
    UserRead, Depends(require_permission(Permission.USERS_EDIT_EMPLOYMENT))
]

SELF_EDITABLE_FIELDS = {
    'name',
    'username',
    'email',
    'birthday',
    'phone',
}

FIELD_PERMISSIONS = {
    'name': Permission.USERS_EDIT_PROFILE,
    'username': Permission.USERS_EDIT_PROFILE,
    'cpf': Permission.USERS_EDIT_PROFILE,
    'email': Permission.USERS_EDIT_PROFILE,
    'birthday': Permission.USERS_EDIT_PROFILE,
    'phone': Permission.USERS_EDIT_PROFILE,
    'unidade': Permission.USERS_EDIT_EMPLOYMENT,
    'subunidade': Permission.USERS_EDIT_EMPLOYMENT,
    'hiring_date': Permission.USERS_EDIT_EMPLOYMENT,
    'termination_date': Permission.USERS_EDIT_EMPLOYMENT,
    'active': Permission.USERS_EDIT_EMPLOYMENT,
    'gross_salary': Permission.USERS_EDIT_SALARY,
}


def _build_meta(total: int, limit: int, offset: int) -> PageMeta:
    total_pages = math.ceil(total / limit) if limit > 0 else 1
    page = (offset // limit) + 1 if limit > 0 else 1
    return PageMeta(
        total=total,
        page=page,
        size=limit,
        total_pages=total_pages,
        has_next=(offset + limit) < total,
        has_prev=offset > 0,
        offset=offset,
    )


async def _load_active_user(session: Session, user_id: int) -> User:
    db_user = await session.scalar(
        select(User)
        .options(selectinload(User.role_assignments))
        .where((User.id == user_id) & User.active)
    )
    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user_id}).',
        )
    return db_user


def _ensure_can_assign_roles(
    actor: UserRead, requested_roles: set[Role]
) -> None:
    if not has_permission(actor.roles, Permission.USERS_ASSIGN_ROLES):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=DENIED)

    for role in requested_roles:
        if not can_assign_role(actor.roles, role):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail='Acesso negado: você não pode atribuir este perfil.',
            )


def _ensure_can_target_official(actor: UserRead, db_user: User) -> None:
    """Somente o próprio oficial pode alterar a conta do oficial.

    Sem isso, um suboficial poderia trocar o e-mail do oficial e usar o
    fluxo de recuperação de senha para assumir a conta.
    """
    if db_user.id != actor.id and Role.OFICIAL in db_user.roles:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=(
                'Acesso negado: a conta do oficial só pode ser alterada '
                'pelo próprio oficial.'
            ),
        )


async def _ensure_not_last_active_official(
    session: Session, db_user: User
) -> None:
    officials = (
        await session.scalar(
            select(func.count())
            .select_from(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(
                User.active,
                UserRole.role == Role.OFICIAL,
                User.id != db_user.id,
            )
        )
        or 0
    )
    if officials == 0:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Não é possível remover o último oficial ativo.',
        )


def _serialize_self(user: User) -> UserSelf:
    data = UserSelf.model_validate(user)
    data.permissions = sorted(
        permissions_for_roles(user.roles), key=lambda item: item.value
    )
    return data


def _apply_field_updates(
    actor: UserRead, db_user: User, update_data: dict, is_self: bool
) -> None:
    for field, value in update_data.items():
        if value is None:
            continue

        if field in SELF_EDITABLE_FIELDS and is_self:
            setattr(db_user, field, value)
            continue

        if not has_permission(actor.roles, FIELD_PERMISSIONS[field]):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail='Acesso negado: sem permissão para alterar este campo.',
            )

        setattr(db_user, field, value)


async def _apply_role_updates(
    session: Session,
    actor: UserRead,
    db_user: User,
    requested_roles: list[Role],
    is_self: bool,
) -> None:
    if is_self:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: você não pode alterar seus perfis.',
        )

    requested = set(requested_roles)
    current = set(db_user.roles)
    _ensure_can_assign_roles(actor, requested ^ current)

    if Role.OFICIAL in current - requested and db_user.active:
        await _ensure_not_last_active_official(session, db_user)

    for assignment in list(db_user.role_assignments):
        if assignment.role not in requested:
            db_user.role_assignments.remove(assignment)

    for role in requested - current:
        db_user.role_assignments.append(
            UserRole(
                user_id=db_user.id,
                role=role,
                granted_by_id=actor.id,
            )
        )


@router.post('/', status_code=HTTPStatus.CREATED, response_model=UserRead)
async def create_user(
    session: Session,
    user: UserCreate,
    current_user: CanCreateUser,
):
    if user.roles:
        _ensure_can_assign_roles(current_user, set(user.roles))

    if user.gross_salary is not None and not has_permission(
        current_user.roles, Permission.USERS_EDIT_SALARY
    ):
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: sem permissão para definir salário.',
        )

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

    data = user.model_dump(exclude={'roles'})
    data['password'] = get_password_hash(data['password'])

    db_user = User(**data)
    session.add(db_user)

    try:
        await session.flush()
        for role in set(user.roles):
            session.add(
                UserRole(
                    user_id=db_user.id,
                    role=role,
                    granted_by_id=current_user.id,
                )
            )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Username, Email ou CPF já existem.',
        )

    await session.refresh(db_user)
    await session.refresh(db_user, ['role_assignments'])
    return db_user


@router.get('/', response_model=PaginatedUserList)
async def read_users(
    session: Session,
    params: Annotated[UserQueryParams, Depends()],
    current_user: CanReadSensitive,
):
    return await _paginated_users(session, params, UserRead)


@router.get('/directory', response_model=PaginatedUserDirectory)
async def read_user_directory(
    session: Session,
    params: Annotated[UserQueryParams, Depends()],
    current_user: CanReadDirectory,
):
    return await _paginated_users(session, params, UserPublic)


async def _paginated_users(session: Session, params: UserQueryParams, schema):
    limit = max(1, params.limit)
    offset = max(0, params.offset)

    filters = [User.active]

    if params.search:
        search_pattern = f'%{params.search}%'
        filters.append(
            or_(
                User.name.ilike(search_pattern),
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
            )
        )

    total = (
        await session.scalar(
            select(func.count()).select_from(User).where(*filters)
        )
        or 0
    )

    users = (
        await session.scalars(
            select(User)
            .options(selectinload(User.role_assignments))
            .where(*filters)
            .order_by(User.name)
            .offset(offset)
            .limit(limit)
        )
    ).all()

    meta = _build_meta(total, limit, offset)
    return {'meta': meta, 'users': [schema.model_validate(u) for u in users]}


@router.get('/me', response_model=UserSelf)
async def get_current_user_data(current_user: CurrentUser):
    return _serialize_self(current_user)


@router.get('/{user_id}', response_model=UserRead)
async def get_user_by_id(
    user_id: int,
    session: Session,
    current_user: CurrentUser,
):
    if current_user.id != user_id and not has_permission(
        current_user.roles, Permission.USERS_READ_SENSITIVE
    ):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=DENIED)

    return await _load_active_user(session, user_id)


@router.put('/{user_id}', response_model=UserRead, status_code=HTTPStatus.OK)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    session: Session,
    current_user: CurrentUser,
):
    db_user = await _load_active_user(session, user_id)
    is_self = db_user.id == current_user.id

    _ensure_can_target_official(current_user, db_user)

    if not is_self and not has_permission(
        current_user.roles, Permission.USERS_EDIT_PROFILE
    ):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=DENIED)

    update_data = user_data.model_dump(exclude_unset=True)
    requested_roles = update_data.pop('roles', None)

    _apply_field_updates(current_user, db_user, update_data, is_self)

    if update_data.get('active') is True:
        db_user.termination_date = None

    if requested_roles is not None:
        await _apply_role_updates(
            session, current_user, db_user, requested_roles, is_self
        )

    if update_data.get('active') is False:
        if Role.OFICIAL in db_user.roles:
            await _ensure_not_last_active_official(session, db_user)

    try:
        await session.commit()
        await session.refresh(db_user)
        await session.refresh(db_user, ['role_assignments'])
        return db_user

    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Username, Email ou CPF já existem.',
        )


@router.delete('/{user_id}', status_code=HTTPStatus.NO_CONTENT)
async def deactivate_user(
    user_id: int,
    session: Session,
    current_user: CanEditEmployment,
):
    db_user = await session.scalar(select(User).where(User.id == user_id))

    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user_id}).',
        )

    if db_user.id == current_user.id:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Não é possível desativar o próprio usuário.',
        )

    _ensure_can_target_official(current_user, db_user)

    if not db_user.active:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f'Usuário com id ({user_id}) já está inativo.',
        )

    db_user.active = False
    await session.commit()


@router.post(
    '/{user_id}/change-password',
    response_model=ChangePasswordResponse,
    status_code=HTTPStatus.OK,
)
async def change_password(
    user_id: int,
    passwords: UserChangePassword,
    request: Request,
    session: Session,
    current_user: CurrentUser,
):
    db_user = await session.scalar(select(User).where(User.id == user_id))

    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user_id}).',
        )

    is_self = current_user.id == db_user.id

    if not is_self and not has_permission(
        current_user.roles, Permission.USERS_CHANGE_PASSWORD
    ):
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=DENIED)

    if is_self:
        if not passwords.old_password:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail='Senha antiga obrigatória.',
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

    keep_jti = (
        refresh_token_jti(request.cookies.get(settings.REFRESH_COOKIE_NAME))
        if is_self
        else None
    )

    db_user.password = get_password_hash(passwords.new_password)
    db_user.password_changed_at = datetime.now(UTC)
    await delete_user_tokens(session, db_user.id, keep_jti=keep_jti)
    await session.commit()

    access_token = (
        create_access_token(data={'sub': db_user.username})
        if is_self
        else None
    )

    return {
        'message': 'Senha alterada com sucesso',
        'access_token': access_token,
    }
