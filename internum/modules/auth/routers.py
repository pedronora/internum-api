from http import HTTPStatus
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import get_session
from internum.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from internum.core.settings import Settings
from internum.modules.auth.schemas import Token
from internum.modules.users.models import User

router = APIRouter(prefix='/auth', tags=['Auth'])

OAuth2Form = Annotated[OAuth2PasswordRequestForm, Depends()]
Session = Annotated[AsyncSession, Depends(get_session)]
settings = Settings()


@router.post('/token', response_model=Token)
async def login_for_access_token(
    response: Response,
    form_data: OAuth2Form,
    session: Session,
):
    user = await session.scalar(
        select(User).where(User.username == form_data.username)
    )

    if not user or not user.active:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Email ou senha incorretos',
        )

    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Email ou senha incorretos',
        )

    access_token = create_access_token(data={'sub': user.username})
    refresh_token = create_refresh_token(data={'sub': user.username})

    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.SECURE_COOKIE,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        expires=settings.REFRESH_COOKIE_MAX_AGE,
        path=settings.REFRESH_COOKIE_PATH,
    )
    return {'access_token': access_token, 'token_type': 'bearer'}


@router.post('/refresh_token', response_model=Token)
async def refresh_access_token(
    request: Request, response: Response, session: Session
):
    refresh_token: Optional[str] = request.cookies.get(
        settings.REFRESH_COOKIE_NAME
    )

    if not refresh_token:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Refresh token ausente',
        )

    try:
        payload = decode_token(refresh_token)
    except HTTPException as exc:
        raise exc

    if payload.get('type') != 'refresh':
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Token inválido para refresh',
        )

    subject_username = payload.get('sub')
    if not subject_username:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail='Token inválido'
        )

    user = await session.scalar(
        select(User).where(User.username == subject_username)
    )
    if not user or not user.active:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail='Usuário inválido'
        )

    new_access_token = create_access_token(data={'sub': user.username})

    return {'access_token': new_access_token, 'token_type': 'bearer'}


@router.post('/logout', status_code=HTTPStatus.NO_CONTENT)
async def logout(response: Response):
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=None,
        secure=settings.SECURE_COOKIE,
        httponly=True,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
