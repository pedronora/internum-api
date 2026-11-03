from datetime import UTC, datetime
from http import HTTPStatus

from fastapi import HTTPException
from jwt import InvalidTokenError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.security import create_refresh_token, decode_token
from internum.modules.auth.models import RefreshToken
from internum.modules.users.models import User

INVALID_REFRESH_TOKEN = 'Refresh token inválido'


def _now() -> datetime:
    return datetime.now(UTC)


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail=INVALID_REFRESH_TOKEN,
    )


async def issue_refresh_token(session: AsyncSession, user: User) -> str:
    token = create_refresh_token(data={'sub': user.username})
    payload = decode_token(token, expected_type='refresh')

    session.add(
        RefreshToken(
            jti=payload['jti'],
            user_id=user.id,
            expires_at=datetime.fromtimestamp(payload['exp'], UTC),
        )
    )

    return token


async def rotate_refresh_token(
    session: AsyncSession, token: str
) -> tuple[str, User]:
    try:
        payload = decode_token(token, expected_type='refresh')
    except InvalidTokenError as exc:
        raise _invalid_refresh_token() from exc

    jti = payload.get('jti')

    if not jti:
        raise _invalid_refresh_token()

    db_token = await session.scalar(
        select(RefreshToken).where(RefreshToken.jti == jti).with_for_update()
    )

    if db_token is None:
        raise _invalid_refresh_token()

    if db_token.rotated_at is not None:
        await delete_user_tokens(session, db_token.user_id)
        await session.commit()
        raise _invalid_refresh_token()

    if db_token.is_expired():
        raise _invalid_refresh_token()

    user = await session.get(User, db_token.user_id)

    if user is None or not user.active:
        raise _invalid_refresh_token()

    db_token.rotated_at = _now()
    new_token = await issue_refresh_token(session, user)
    await session.commit()

    return new_token, user


async def delete_refresh_token(session: AsyncSession, token: str) -> None:
    try:
        payload = decode_token(token)
    except HTTPException:
        return

    jti = payload.get('jti')

    if not jti:
        return

    await session.execute(delete(RefreshToken).where(RefreshToken.jti == jti))
    await session.commit()


async def delete_user_tokens(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        delete(RefreshToken).where(RefreshToken.user_id == user_id)
    )
