from collections.abc import Callable
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException

from internum.core.authorization import Permission, has_permission
from internum.core.security import get_current_user
from internum.modules.users.schemas import UserRead

DENIED = 'Acesso negado: usuário sem permissão'

CurrentUser = Annotated[UserRead, Depends(get_current_user)]


def require_permission(permission: Permission) -> Callable:
    def dependency(current_user: CurrentUser) -> UserRead:
        if not has_permission(current_user.roles, permission):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail=DENIED
            )
        return current_user

    return dependency


def require_self_or_permission(permission: Permission) -> Callable:
    def dependency(current_user: CurrentUser, user_id: int) -> UserRead:
        if current_user.id == user_id:
            return current_user
        if has_permission(current_user.roles, permission):
            return current_user
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=DENIED)

    return dependency
