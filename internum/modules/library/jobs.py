from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.core.database import async_session_maker
from internum.modules.library.enums import LoanStatus
from internum.modules.library.models import Loan


async def check_overdue_loans():
    print(f'[Scheduler] Verificando empréstimos vencidos às {datetime.now()}')

    async with async_session_maker() as session:
        await _mark_overdue_loans(session)


async def _mark_overdue_loans(session: AsyncSession):
    today = datetime.utcnow().date()
    loans = await session.scalars(
        select(Loan).where(
            Loan.status == LoanStatus.BORROWED, Loan.borrowed_at < today
        )
    )

    updated_count = 0

    for loan in loans:
        loan.check_overdue()
        if loan.status == LoanStatus.LATE:
            updated_count += 1

    if updated_count > 0:
        await session.commit()
        print(
            f'[Scheduler] {updated_count} empréstimos marcados como vencidos.'
        )
    else:
        print('[Scheduler] Nenhum empréstimo vencido encontrado.')
