from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from internum.modules.auth.jobs import delete_expired_reset_tokens
from internum.modules.library.jobs import check_overdue_loans
from internum.modules.vacation.jobs import ensure_accrual_periods_job

scheduler = AsyncIOScheduler()


def start_scheduler():
    timezone_sp = ZoneInfo('America/Sao_Paulo')

    scheduler.add_job(
        check_overdue_loans,
        CronTrigger(hour=00, minute=00, timezone=timezone_sp),
        id='check_overdue_loans',
        name='Verificar empréstimos vencidos',
    )

    scheduler.add_job(
        delete_expired_reset_tokens,
        CronTrigger(hour=00, minute=00, timezone=timezone_sp),
        id='delete_expired_tokens',
        name='Deletar tokens expirados',
    )

    scheduler.add_job(
        ensure_accrual_periods_job,
        CronTrigger(hour=00, minute=00, timezone=timezone_sp),
        id='ensure_accrual_periods',
        name='Sincronizar períodos aquisitivos',
    )

    scheduler.start()
