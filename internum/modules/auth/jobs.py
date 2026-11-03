from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import async_session_maker
from internum.core.settings import Settings
from internum.modules.auth.models import PasswordResetToken, RefreshToken

settings = Settings()


async def _delete_expired_reset_tokens(session: AsyncSession):
    print(
        '[Scheduler] Verificando tokens usados ou vencidos '
        f'às {datetime.now(UTC)}'
    )

    today = datetime.now(UTC)
    result = await session.execute(
        delete(PasswordResetToken).where(PasswordResetToken.expires_at < today)
    )

    deleted_count = result.rowcount
    print(f'[Scheduler] Foram deletados {deleted_count} tokens.')
    await session.commit()


async def delete_expired_reset_tokens():
    async with async_session_maker() as session:
        try:
            await _delete_expired_reset_tokens(session)
        except Exception as e:
            print(f'[Scheduler] Erro ao deletar tokens: {e}')
            await session.rollback()


async def _delete_expired_refresh_tokens(session: AsyncSession):
    print(
        '[Scheduler] Verificando refresh tokens vencidos '
        f'às {datetime.now(UTC)}'
    )

    today = datetime.now(UTC)
    session_cutoff = today - timedelta(
        days=settings.REFRESH_TOKEN_ABSOLUTE_DAYS
    )

    result = await session.execute(
        delete(RefreshToken).where(
            or_(
                RefreshToken.expires_at < today,
                RefreshToken.session_started_at < session_cutoff,
            )
        )
    )

    deleted_count = result.rowcount
    print(f'[Scheduler] Foram deletados {deleted_count} refresh tokens.')
    await session.commit()


async def delete_expired_refresh_tokens():
    async with async_session_maker() as session:
        try:
            await _delete_expired_refresh_tokens(session)
        except Exception as e:
            print(f'[Scheduler] Erro ao deletar refresh tokens: {e}')
            await session.rollback()
