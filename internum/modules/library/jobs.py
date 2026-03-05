import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import async_session_maker
from internum.core.email import EmailService
from internum.modules.library.enums import LoanStatus
from internum.modules.library.models import Loan
from internum.modules.library.templates import loan_late_template

email_service = EmailService()


async def check_overdue_loans():
    print(
        '[Scheduler] Verificando empréstimos vencidos às '
        f'{datetime.now(timezone.utc)}'
    )
    async with async_session_maker() as session:
        await _mark_overdue_loans(session)


async def _mark_overdue_loans(session: AsyncSession):
    """Marca empréstimos vencidos e envia email de aviso."""
    today = datetime.utcnow()
    result = await session.scalars(
        select(Loan)
        .options(selectinload(Loan.book), selectinload(Loan.created_by))
        .where(
            Loan.status == LoanStatus.BORROWED,
            Loan.due_date < today,
        )
    )
    loans = result.all()

    updated_count = 0

    for loan in loans:
        if loan.check_overdue():
            await asyncio.to_thread(send_alert_late_loan, loan)
            updated_count += 1

    if updated_count > 0:
        await session.commit()
        print(
            f'[Scheduler] {updated_count} empréstimos marcados como vencidos.'
        )
    else:
        print('[Scheduler] Nenhum empréstimo vencido encontrado.')


def send_alert_late_loan(loan: Loan):
    alert_str = (
        datetime.now(timezone.utc)
        .astimezone(ZoneInfo('America/Sao_Paulo'))
        .strftime('%d/%m/%Y, %H:%M:%S')
    )

    due_dt = loan.due_date.replace(tzinfo=timezone.utc)
    due_str = due_dt.astimezone(ZoneInfo('America/Sao_Paulo')).strftime(
        '%d/%m/%Y'
    )

    html_content = loan_late_template(
        user_name=loan.created_by.name,
        book_title=loan.book.title,
        book_author=loan.book.author,
        due_date_str=due_str,
        alert_str=alert_str,
    )

    email_service.send_email(
        email_to=[loan.created_by.email],
        subject='[Internum] Aviso de Empréstimo Atrasado',
        html=html_content,
        category='Loan Late',
    )
