import uuid
from datetime import datetime, timedelta
from http import HTTPStatus
from zoneinfo import ZoneInfo

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt import DecodeError, ExpiredSignatureError, decode, encode
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = _now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire})
    encoded_jwt = encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(data: dict):
    to_encode = data.copy()
    jti = uuid.uuid4().hex
    expire = _now_utc() + timedelta(
        days=getattr(settings, 'REFRESH_TOKEN_EXPIRE_DAYS', 7)
    )
    to_encode.update({'exp': expire, 'jti': jti, 'type': 'refresh'})
    encoded_jwt = encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def get_password_hash(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


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

    except DecodeError:
        raise credentials_exception

    except ExpiredSignatureError:
        raise credentials_exception

    user = await session.scalar(
        select(User).where(User.username == subject_username)
    )

    if not user or not user.active:
        raise credentials_exception

    return user
