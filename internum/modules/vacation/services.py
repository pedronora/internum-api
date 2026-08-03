from datetime import date, datetime, timedelta
from typing import Optional

import holidays
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from internum.modules.users.models import User
from internum.modules.vacation.enums import (
    VacationPeriodType,
    VacationRequestStatus,
    VacationStatus,
)
from internum.modules.vacation.models import (
    VacationBalance,
    VacationPeriod,
    VacationRequest,
)
from internum.modules.vacation.schemas import (
    VacationPeriodCreate,
    VacationPreviewRequest,
    VacationPreviewResponse,
)


class CLTVacationService:
    BRAZIL_HOLIDAYS = holidays.Brazil(state='PR')

    MIN_PERIOD_DAYS = 5
    MIN_MAIN_PERIOD_DAYS = 14
    MAX_PERIODS = 3
    MAX_SELL_DAYS = 10
    VACATION_DAYS_PER_YEAR = 30

    WEEKEND_DAYS = {5, 6}

    def __init__(self, session: AsyncSession):
        self.session = session

    def is_holiday(self, dt: date) -> bool:
        return dt in self.BRAZIL_HOLIDAYS

    @staticmethod
    def is_weekend(dt: date) -> bool:
        return dt.weekday() in CLTVacationService.WEEKEND_DAYS

    def is_business_day(self, dt: date) -> bool:
        return not self.is_weekend(dt) and not self.is_holiday(dt)

    @staticmethod
    def count_calendar_days(start: date, end: date) -> int:
        return (end - start).days + 1

    def count_working_days(self, start: date, end: date) -> int:
        count = 0
        current = start
        while current <= end:
            if self.is_business_day(current):
                count += 1
            current += timedelta(days=1)
        return count

    def validate_period_dates(self, start: date, end: date) -> list[str]:
        errors = []

        if self.is_weekend(start):
            errors.append(
                f'Início ({start.strftime("%d/%m/%Y")}) '
                'não pode ser em fim de semana'
            )

        if self.is_holiday(start):
            errors.append(
                f'Início ({start.strftime("%d/%m/%Y")}) '
                f'não pode ser em feriado: {self.BRAZIL_HOLIDAYS.get(start)}'
            )

        if self.is_weekend(end):
            errors.append(
                f'Fim ({end.strftime("%d/%m/%Y")}) '
                'não pode ser em fim de semana'
            )

        if self.is_holiday(end):
            errors.append(
                f'Fim ({end.strftime("%d/%m/%Y")}) '
                f'não pode ser em feriado: {self.BRAZIL_HOLIDAYS.get(end)}'
            )

        calendar_days = self.count_calendar_days(start, end)
        if calendar_days < self.MIN_PERIOD_DAYS:
            errors.append(
                f'Período deve ter no mínimo {self.MIN_PERIOD_DAYS} '
                f'dias corridos (tem {calendar_days})'
            )

        working_days = self.count_working_days(start, end)
        if working_days < self.MIN_PERIOD_DAYS:
            errors.append(
                f'Período deve ter no mínimo {self.MIN_PERIOD_DAYS} '
                f'dias úteis (tem {working_days})'
            )

        return errors

    def validate_periods_clt(
        self, periods: list[VacationPeriodCreate], hiring_date: date
    ) -> list[str]:
        errors = []

        if len(periods) > self.MAX_PERIODS:
            errors.append(
                f'Máximo de {self.MAX_PERIODS} períodos de férias permitidos'
            )

        if not periods:
            errors.append('Pelo menos um período de férias é obrigatório')
            return errors

        for i, period in enumerate(periods):
            period_errors = self.validate_period_dates(
                period.start_date, period.end_date
            )
            errors.extend([f'Período {i + 1}: {e}' for e in period_errors])

        sorted_periods = sorted(periods, key=lambda p: p.start_date)
        for i in range(len(sorted_periods) - 1):
            current_end = sorted_periods[i].end_date
            next_start = sorted_periods[i + 1].start_date
            if next_start <= current_end:
                errors.append(
                    'Período '
                    f'{i + 2} deve começar após o fim do período {i + 1}'
                )
            elif (next_start - current_end).days < 1:
                errors.append('Deve haver pelo menos 1 dia entre períodos')

        main_periods = [
            p
            for p in periods
            if self.count_calendar_days(p.start_date, p.end_date)
            >= self.MIN_MAIN_PERIOD_DAYS
        ]
        if not main_periods:
            errors.append(
                f'Pelo menos um período deve ter {self.MIN_MAIN_PERIOD_DAYS} '
                'dias ou mais (Art. 134 CLT)'
            )

        total_working_days = sum(
            self.count_working_days(p.start_date, p.end_date) for p in periods
        )
        if total_working_days > self.VACATION_DAYS_PER_YEAR:
            errors.append(
                'Total de dias úteis '
                f'({total_working_days}) excede o máximo de '
                f'{self.VACATION_DAYS_PER_YEAR} dias por período aquisitivo'
            )

        return errors

    async def calculate_balance(self, user: User) -> VacationBalance:
        balance = await self.session.scalar(
            select(VacationBalance).where(VacationBalance.user_id == user.id)
        )

        if not balance:
            balance = await self._create_initial_balance(user)

        await self._update_balance_periods(balance, user)
        return balance

    async def _create_initial_balance(self, user: User) -> VacationBalance:
        today = date.today()
        hiring = user.hiring_date

        period_start = hiring
        period_end = date(today.year, hiring.month, hiring.day)
        if period_end < today:
            period_end = date(today.year + 1, hiring.month, hiring.day)

        next_start = period_end + timedelta(days=1)
        next_end = date(
            next_start.year + 1, hiring.month, hiring.day
        ) - timedelta(days=1)

        years_worked = (today - hiring).days / 365.25
        accrued = min(
            int(years_worked) * self.VACATION_DAYS_PER_YEAR,
            self.VACATION_DAYS_PER_YEAR,
        )

        balance = VacationBalance(
            user_id=user.id,
            current_period_start=period_start,
            current_period_end=period_end,
            accrued_days=accrued,
            proportional_days=0,
            enjoyed_days=0,
            sold_days=0,
            next_period_start=next_start,
            next_period_end=next_end,
            next_accrued_days=0,
        )
        self.session.add(balance)
        await self.session.flush()
        return balance

    async def _update_balance_periods(
        self, balance: VacationBalance, user: User
    ) -> None:
        today = date.today()
        hiring = user.hiring_date

        if today > balance.current_period_end:
            years_completed = (balance.current_period_end - hiring).days // 365
            next_year_start = date(
                hiring.year + years_completed + 1, hiring.month, hiring.day
            )
            next_year_end = date(
                next_year_start.year + 1, hiring.month, hiring.day
            ) - timedelta(days=1)

            balance.current_period_start = next_year_start
            balance.current_period_end = next_year_end
            balance.accrued_days = self.VACATION_DAYS_PER_YEAR
            balance.proportional_days = 0
            balance.enjoyed_days = 0
            balance.sold_days = 0

            balance.next_period_start = next_year_end + timedelta(days=1)
            balance.next_period_end = date(
                balance.next_period_start.year + 1, hiring.month, hiring.day
            ) - timedelta(days=1)

    async def preview_vacation(
        self, user: User, request: VacationPreviewRequest
    ) -> VacationPreviewResponse:
        balance = await self.calculate_balance(user)
        errors = self.validate_periods_clt(request.periods, user.hiring_date)

        if errors:
            return VacationPreviewResponse(valid=False, errors=errors)

        warnings = []
        total_days = 0
        total_working_days = 0
        periods_detail = []

        for i, period in enumerate(request.periods):
            cal_days = self.count_calendar_days(
                period.start_date, period.end_date
            )
            work_days = self.count_working_days(
                period.start_date, period.end_date
            )

            period_errors = self.validate_period_dates(
                period.start_date, period.end_date
            )
            if period_errors:
                errors.extend(
                    [f'Período {i + 1}: {e}' for e in period_errors]
                )

            if cal_days >= self.MIN_MAIN_PERIOD_DAYS:
                period_type = VacationPeriodType.FULL
            else:
                period_type = VacationPeriodType.PROPORTIONAL

            periods_detail.append(
                {
                    'index': i + 1,
                    'start_date': period.start_date.isoformat(),
                    'end_date': period.end_date.isoformat(),
                    'calendar_days': cal_days,
                    'working_days': work_days,
                    'period_type': period_type.value,
                }
            )

            total_days += cal_days
            total_working_days += work_days

        if total_working_days > balance.available_days:
            errors.append(
                'Dias úteis solicitados '
                f'({total_working_days}) excedem saldo disponível '
                f'({balance.available_days})'
            )

        if (
            balance.accrued_days > 0
            and total_working_days > balance.accrued_days
        ):
            warnings.append(
                'Férias incluem dias proporcionais '
                '(período aquisitivo não completado)'
            )

        return VacationPreviewResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            total_days=total_days,
            total_working_days=total_working_days,
            periods_detail=periods_detail,
        )

    async def create_request(
        self, user: User, periods: list[VacationPeriodCreate]
    ) -> VacationRequest:
        preview = await self.preview_vacation(
            user, VacationPreviewRequest(periods=periods)
        )
        if not preview.valid:
            raise ValueError('; '.join(preview.errors))

        request = VacationRequest(
            user_id=user.id,
            status=VacationRequestStatus.SUBMITTED,
            requested_at=datetime.now(),
        )
        self.session.add(request)
        await self.session.flush()

        for period_data in periods:
            cal_days = self.count_calendar_days(
                period_data.start_date, period_data.end_date
            )
            work_days = self.count_working_days(
                period_data.start_date, period_data.end_date
            )

            period_type = (
                VacationPeriodType.FULL
                if cal_days >= self.MIN_MAIN_PERIOD_DAYS
                else VacationPeriodType.PROPORTIONAL
            )

            period = VacationPeriod(
                request_id=request.id,
                start_date=period_data.start_date,
                end_date=period_data.end_date,
                period_type=period_type,
                status=VacationStatus.PENDING,
                days_count=cal_days,
                working_days_count=work_days,
            )
            self.session.add(period)

        await self.session.flush()
        return request

    async def approve_request(
        self,
        request: VacationRequest,
        reviewer: User,
        reviewer_notes: Optional[str] = None,
    ) -> VacationRequest:
        if request.status != VacationRequestStatus.SUBMITTED:
            raise ValueError('Solicitação não está pendente de aprovação')

        balance = await self.calculate_balance(request.user)
        total_work_days = sum(p.working_days_count for p in request.periods)

        if total_work_days > balance.available_days:
            raise ValueError(
                'Saldo insuficiente. Disponível: '
                f'{balance.available_days}, Solicitado: {total_work_days}'
            )

        request.status = VacationRequestStatus.APPROVED
        request.reviewer_id = reviewer.id
        request.reviewed_at = datetime.now()
        request.reviewer_notes = reviewer_notes

        for period in request.periods:
            period.status = VacationStatus.APPROVED

        balance.enjoyed_days += total_work_days

        await self.session.flush()
        return request

    async def reject_request(
        self,
        request: VacationRequest,
        reviewer: User,
        reviewer_notes: Optional[str] = None,
    ) -> VacationRequest:
        invalid_statuses = {
            VacationRequestStatus.SUBMITTED,
            VacationRequestStatus.UNDER_REVIEW,
        }
        if request.status not in invalid_statuses:
            raise ValueError('Solicitação não pode ser rejeitada')

        request.status = VacationRequestStatus.REJECTED
        request.reviewer_id = reviewer.id
        request.reviewed_at = datetime.now()
        request.reviewer_notes = reviewer_notes

        for period in request.periods:
            period.status = VacationStatus.REJECTED

        await self.session.flush()
        return request

    async def cancel_request(
        self, request: VacationRequest, user: User
    ) -> VacationRequest:
        if request.user_id != user.id:
            raise ValueError('Não pode cancelar solicitação de outro usuário')

        cancellable_statuses = {
            VacationRequestStatus.SUBMITTED,
            VacationRequestStatus.UNDER_REVIEW,
        }
        if request.status not in cancellable_statuses:
            raise ValueError('Solicitação não pode ser cancelada')

        request.status = VacationRequestStatus.CANCELLED

        for period in request.periods:
            if period.status == VacationStatus.APPROVED:
                period.status = VacationStatus.CANCELLED
            elif period.status == VacationStatus.PENDING:
                period.status = VacationStatus.CANCELLED

        await self.session.flush()
        return request

    async def sell_vacation_days(
        self, user: User, days: int
    ) -> VacationBalance:
        if days > self.MAX_SELL_DAYS:
            raise ValueError(
                f'Máximo {self.MAX_SELL_DAYS} dias podem ser vendidos'
            )

        balance = await self.calculate_balance(user)

        if days > balance.accrued_days:
            raise ValueError(
                f'Apenas {balance.accrued_days} dias vencidos '
                'disponíveis para venda'
            )

        balance.sold_days += days
        balance.accrued_days -= days

        await self.session.flush()
        return balance

    async def adjust_balance(
        self,
        user: User,
        adjuster: User,
        adjustment_days: int,
        reason: str,
    ) -> VacationBalance:
        """Ajuste manual de saldo (apenas admin) - para migração/histórico."""
        balance = await self.calculate_balance(user)

        # Validação de negócio: resultado final deve fazer sentido
        final_available = (
            balance.accrued_days
            + balance.proportional_days
            + adjustment_days
            - balance.enjoyed_days
            - balance.sold_days
        )

        MAX_ACCRUAL = 180  # teto razoável (~6 anos)
        MAX_NEGATIVE = -30  # não pode dever mais que 30 dias

        if final_available > MAX_ACCRUAL:
            raise ValueError(
                f'Ajuste resultaria em {final_available} dias disponíveis. '
                f'Teto máximo: {MAX_ACCRUAL} dias (acúmulo excessivo).'
            )

        if final_available < MAX_NEGATIVE:
            raise ValueError(
                'Ajuste resultaria em '
                f'{final_available} dias disponíveis. '
                f'Não pode exceder {MAX_NEGATIVE} dias negativos '
                '(débito excessivo).'
            )

        balance.manual_adjustment_days = adjustment_days
        balance.adjustment_reason = reason
        balance.adjusted_at = datetime.now()
        balance.adjusted_by_id = adjuster.id

        await self.session.flush()
        return balance
