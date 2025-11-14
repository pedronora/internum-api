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
        .options(selectinload(Loan.book), selectinload(Loan.user))
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

    html_content = f"""
    <html>
      <body
      style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4CAF50;">Aviso de Empréstimo Atrasado</h2>
        <p>Olá, {loan.user.name}:</p>
        <p>O empréstimo abaixo está atrasado:</p>
        <h3>Detalhes do Livro:</h3>
        <ul>
          <li><strong>Título:</strong> {loan.book.title}</li>
          <li><strong>Autor:</strong> {loan.book.author}</li>
          <li><strong>Data da devolução:</strong> {due_str}</li>
        </ul>
        <p><strong>Data/Hora do aviso:</strong> {alert_str}</p>
        <hr>
    <p style="font-size: 0.9em; color: #888;">
    Esta é uma mensagem automática do sistema Internum - 1º SRI de Cascavel/PR.
    </p>
      </body>
    </html>
    """

    email_service.send_email(
        email_to=[loan.user.email],
        subject='[Internhum] Aviso de Empréstimo Atrasado',
        html=html_content,
        category='Loan Late',
    )
