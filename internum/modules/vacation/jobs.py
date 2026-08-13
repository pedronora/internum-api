from internum.core.database import async_session_maker
from internum.modules.vacation.services import CLTVacationService


async def ensure_accrual_periods_job():
    """Sincroniza períodos aquisitivos de todos os usuários ativos."""
    print('[Scheduler] Sincronizando períodos aquisitivos...')
    async with async_session_maker() as session:
        service = CLTVacationService(session)
        await service.ensure_all_users_accrual_periods()
        await session.commit()
    print('[Scheduler] Períodos aquisitivos sincronizados.')
