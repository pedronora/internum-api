from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from internum.modules.library.jobs import check_overdue_loans

scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(check_overdue_loans, CronTrigger(hour=3, minute=00))

    scheduler.start()
