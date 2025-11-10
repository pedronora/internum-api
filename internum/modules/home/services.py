from datetime import date, datetime
from typing import Annotated, Sequence

from fastapi import Depends
from sqlalchemy import and_, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.modules.home.schemas import HomeSummary, UnreadNoticesSummary
from internum.modules.legal_briefs.models import LegalBrief
from internum.modules.library.models import Loan
from internum.modules.library.schemas import LoanStatus
from internum.modules.notices.models import Notice, NoticeRead
from internum.modules.users.models import User

Session = Annotated[AsyncSession, Depends(get_session)]


class HomeService:
    def __init__(self, session: Session):
        self.session = session
        self.today = date.today()

    async def _get_monthly_birthdays(self):
        return (
            await self.session.scalars(
                select(User).where(
                    extract('month', User.birthday) == self.today.month
                )
            )
        ).all()

    async def _get_random_legal_brief(self):
        return await self.session.scalar(
            select(LegalBrief)
            .where(LegalBrief.canceled.is_(False))
            .order_by(func.random())
            .limit(1)
        )

    async def _get_unread_notices_summary(
        self, current_user_id: int, user_created_at: datetime
    ):
        total_unread = await self.session.scalar(
            select(func.count(Notice.id)).where(
                ~Notice.reads.any(
                    and_(
                        NoticeRead.user_id == current_user_id,
                        Notice.created_at > user_created_at,
                    )
                )
            )
        )

        unread_notices_result = await self.session.scalars(
            select(Notice)
            .where(
                ~Notice.reads.any(
                    and_(
                        NoticeRead.user_id == current_user_id,
                        Notice.created_at > user_created_at,
                    )
                )
            )
            .order_by(Notice.created_at.desc())
            .limit(3)
        )

        return UnreadNoticesSummary(
            total=total_unread if total_unread is not None else 0,
            unread_notices=unread_notices_result.all(),
        )

    async def _get_active_loans(self, current_user_id: int) -> Sequence[Loan]:
        loans_result = await self.session.scalars(
            select(Loan)
            .options(selectinload(Loan.book))
            .where(
                (Loan.user_id == current_user_id)
                & (Loan.status.in_([LoanStatus.BORROWED, LoanStatus.LATE]))
            )
        )
        return loans_result.all()

    async def get_summary_data(
        self, current_user_id: int, user_created_at: datetime
    ):
        birthdays = await self._get_monthly_birthdays()
        legal_brief = await self._get_random_legal_brief()
        unread_notices = await self._get_unread_notices_summary(
            current_user_id, user_created_at
        )
        loans = await self._get_active_loans(current_user_id)

        return HomeSummary(
            current_month=self.today.strftime('%B'),
            birthdays=birthdays,
            legal_brief=legal_brief,
            unread_notices=unread_notices,
            loans=loans,
        )
