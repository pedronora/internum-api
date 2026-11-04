import hashlib
import uuid
from datetime import datetime, timedelta
from http import HTTPStatus
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import (
    DecodeError,
    ExpiredSignatureError,
    InvalidTokenError,
    decode,
    encode,
)
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.core.settings import Settings
from internum.modules.users.models import User

settings = Settings()
pwd_context = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl='api/v1/auth/token', refreshUrl='api/v1/auth/refresh_token'
)


def _now_utc() -> datetime:
    return datetime.now(tz=ZoneInfo('UTC'))


def create_access_token(
    data: dict,
    expire_minutes: int = settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    purpose: str | None = None,
):
    to_encode = data.copy()
    now = _now_utc()
    expire = now + timedelta(minutes=expire_minutes)
    to_encode.update({'exp': expire, 'iat': now, 'type': 'access'})

    if purpose:
        to_encode['purpose'] = purpose

    encoded_jwt = encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def create_refresh_token(
    data: dict, expire_days: int = settings.REFRESH_TOKEN_EXPIRE_DAYS
):
    to_encode = data.copy()
    jti = uuid.uuid4().hex
    expire = _now_utc() + timedelta(days=expire_days)

    to_encode.update({'exp': expire, 'jti': jti, 'type': 'refresh'})
    encoded_jwt = encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def get_password_hash(password: str):
    return pwd_context.hash(password)


def hash_token(token: str) -> str:
    """Deriva o valor persistido de um token sensível.

    Tokens de reset de senha são credenciais temporárias: guardar apenas o
    hash SHA-256 evita que um vazamento do banco permita redefinir senhas.
    """
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def decode_token(
    token: str,
    expected_purpose: str | None = None,
    expected_type: str | None = None,
):
    try:
        payload = decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )

        if expected_type is not None:
            if payload.get('type') != expected_type:
                raise InvalidTokenError('Tipo do token inválido.')

        if expected_purpose is not None:
            token_purpose = payload.get('purpose')
            if token_purpose != expected_purpose:
                raise InvalidTokenError('Propósito do token inválido.')

        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail='Token expirado.'
        )
    except DecodeError:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail='Token inválido.'
        )


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    token: str = Depends(oauth2_scheme),
):
    credentials_exception = HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail='Não foi possível validar as credenciais',
        headers={'WWW-Authenticate': 'Bearer'},
    )

    try:
        payload = decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        subject_username = payload.get('sub')

        if not subject_username:
            raise credentials_exception

        if payload.get('type') != 'access' or payload.get('purpose'):
            raise credentials_exception

    except DecodeError:
        raise credentials_exception

    except ExpiredSignatureError:
        raise credentials_exception

    user = await session.scalar(
        select(User)
        .options(selectinload(User.role_assignments))
        .where(User.username == subject_username)
    )

    if not user:
        raise credentials_exception

    if not user.active:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Não encontrado usuário com id ({user.id}).',
        )

    issued_at = payload.get('iat')

    if not isinstance(issued_at, (int, float)):
        raise credentials_exception

    if (
        user.password_changed_at is not None
        and issued_at + 1 < user.password_changed_at.timestamp()
    ):
        raise credentials_exception

    return user
