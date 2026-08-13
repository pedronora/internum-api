from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from typing import Annotated, Optional
from zoneinfo import ZoneInfo

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.security import OAuth2PasswordRequestForm
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import get_session
from internum.core.email import EmailService
from internum.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from internum.core.settings import Settings
from internum.modules.auth.models import PasswordResetToken
from internum.modules.auth.schemas import (
    ForgotPasswordRequest,
    Message,
    ResetPasswordRequest,
    Token,
)
from internum.modules.auth.templates import password_reset_template
from internum.modules.users.models import User

router = APIRouter(prefix='/auth', tags=['Auth'])

OAuth2Form = Annotated[OAuth2PasswordRequestForm, Depends()]
Session = Annotated[AsyncSession, Depends(get_session)]

settings = Settings()
email_service = EmailService()


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
            detail='Usuário ou senha incorretos',
        )

    if not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail='Usuário ou senha incorretos',
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


@router.post(
    '/forgot-password',
    status_code=HTTPStatus.OK,
    response_model=Message,
)
async def forgot_password(
    data: ForgotPasswordRequest,
    session: Session,
    background_tasks: BackgroundTasks,
):
    user = await session.scalar(select(User).where(User.email == data.email))

    if not user:
        return {
            'message': 'Se o email existir, enviaremos instruções '
            'para redefinir a senha.'
        }

    reset_token = create_access_token(
        data={'sub': str(user.id)},
        expire_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
        purpose='password_reset',
    )

    db_reset_token = PasswordResetToken(
        user_id=user.id,
        token=reset_token,
        expires_at=datetime.now(UTC)
        + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES),
    )

    session.add(db_reset_token)
    await session.commit()

    reset_link = (
        settings.FRONTEND_URL + '/auth/reset-password?token=' + reset_token
    )

    requested = (
        datetime.now(UTC)
        .astimezone(ZoneInfo('America/Sao_Paulo'))
        .strftime('%d/%m/%Y %H:%M:%S')
    )

    html_content = password_reset_template(
        payload={
            'user_name': user.name,
            'reset_link': reset_link,
            'requested_at': requested,
            'expire_minutes': settings.RESET_TOKEN_EXPIRE_MINUTES,
        }
    )

    background_tasks.add_task(
        email_service.send_email,
        email_to=[user.email],
        subject='[Internum] Recuperação de Senha',
        html=html_content,
        category='Reset Password',
    )

    return {
        'message': 'Se o email existir, enviaremos '
        'instruções para redefinir a senha.'
    }


@router.post(
    '/reset-password', status_code=HTTPStatus.OK, response_model=Message
)
async def reset_password(data: ResetPasswordRequest, session: Session):
    try:
        payload = decode_token(
            data.token,
            expected_purpose='password_reset',
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Token inválido ou expirado.',
        )
    except HTTPException as exc:
        raise exc

    user_id = payload.get('sub')
    if not user_id:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail='Token inválido.'
        )

    db_token = await session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token == data.token
        )
    )

    if not db_token:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Token inválido.',
        )

    if db_token.used:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Este link de redefinição já foi utilizado. '
            'Solicite um novo.',
        )

    db_user = await session.scalar(select(User).where(User.id == int(user_id)))

    if not db_user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail='Usuário não encontrado.'
        )

    if verify_password(data.new_password, db_user.password):
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail='A nova senha não pode ser igual a anterior.',
        )

    db_user.password = get_password_hash(data.new_password)
    db_token.used = True
    await session.commit()

    return {'message': 'Senha redefinida com sucesso.'}
