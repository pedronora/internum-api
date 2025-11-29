from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import async_session_maker
from internum.modules.auth.models import PasswordResetToken


async def _delete_expired_or_used_reset_tokens(session: AsyncSession):
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


async def delete_expired_or_used_reset_tokens():
    async with async_session_maker() as session:
        try:
            await _delete_expired_or_used_reset_tokens(session)
        except Exception as e:
            print(f'[Scheduler] Erro ao deletar tokens: {e}')
            await session.rollback()
