from http import HTTPStatus
from typing import Annotated, Callable

from fastapi import Depends, HTTPException

from internum.core.security import get_current_user
from internum.modules.users.schemas import UserRead

CurrentUser = Annotated[UserRead, Depends(get_current_user)]


def require_self_or_roles(*allowed_roles: str) -> Callable:
    def dependency(
        current_user: CurrentUser,
        user_id: int,
    ) -> UserRead:
        if current_user.id == user_id:
            return current_user

        if current_user.role in allowed_roles:
            return current_user

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: usuário sem permissão',
        )

    return dependency


def require_roles(*allowed_roles: str) -> Callable:
    def dependency(
        current_user: CurrentUser,
    ):
        if current_user.role in allowed_roles:
            return current_user

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Acesso negado: usuário sem permissão',
        )

    return dependency


VerifySelfAdmin = Annotated[UserRead, Depends(require_self_or_roles('admin'))]
VerifySelfAdminCoord = Annotated[
    UserRead, Depends(require_self_or_roles('admin', 'coord'))
]
VerifyAdminCoord = Annotated[
    UserRead, Depends(require_roles('admin', 'coord'))
]
