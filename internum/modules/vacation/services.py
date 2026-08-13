from datetime import date, datetime, timedelta
from typing import Optional

import holidays
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.modules.users.enums import Setor
from internum.modules.users.models import User
from internum.modules.vacation.enums import (
    VacationAccrualStatus,
    VacationAlertType,
    VacationGrantStatus,
    VacationGrantType,
    VacationPeriodType,
    VacationRequestStatus,
)
from internum.modules.vacation.models import (
    VacationAccrualPeriod,
    VacationGrant,
    VacationPeriod,
    VacationRequest,
)
from internum.modules.vacation.schemas import (
    VacationGrantCreate,
    VacationPeriodCreate,
    VacationPreviewRequest,
    VacationPreviewResponse,
    VacationRequestCreate,
)

MAX_PERIODS = 3
VACATION_DAYS_PER_YEAR = 30
MIN_PERIOD_DAYS = 5
MIN_MAIN_PERIOD_DAYS = 14
MAX_SELL_DAYS = 10
ALERT_DAYS_WINDOW = 30


class CLTVacationService:  # noqa: PLR0904
    BRAZIL_HOLIDAYS = holidays.Brazil(state='PR')

    MIN_PERIOD_DAYS = MIN_PERIOD_DAYS
    MIN_MAIN_PERIOD_DAYS = MIN_MAIN_PERIOD_DAYS
    MAX_PERIODS = MAX_PERIODS
    MAX_SELL_DAYS = MAX_SELL_DAYS
    VACATION_DAYS_PER_YEAR = VACATION_DAYS_PER_YEAR

    FRIDAY_WEEKDAY = 4
    SATURDAY_WEEKDAY = 5
    SUNDAY_WEEKDAY = 6

    WEEKEND_DAYS = {SATURDAY_WEEKDAY, SUNDAY_WEEKDAY}

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Helpers de data
    # ------------------------------------------------------------------

    def is_holiday(self, dt: date) -> bool:
        return dt in self.BRAZIL_HOLIDAYS

    @staticmethod
    def is_weekend(dt: date) -> bool:
        return dt.weekday() in CLTVacationService.WEEKEND_DAYS

    @staticmethod
    def count_calendar_days(start: date, end: date) -> int:
        return (end - start).days + 1

    # ------------------------------------------------------------------
    # Períodos aquisitivos
    # ------------------------------------------------------------------

    @staticmethod
    def _anniversary(hiring: date, offset: int) -> date:
        """Aniversário de contratação com `offset` anos de diferença."""
        year = hiring.year + offset
        month = hiring.month
        day = hiring.day
        if month == 2 and day == 29:  # noqa: PLR2004
            if not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
                day = 28
        return date(year, month, day)

    @classmethod
    def _period_dates(
        cls, hiring: date, period_number: int
    ) -> tuple[date, date, date, date]:
        acquisitive_start = cls._anniversary(hiring, period_number - 1)
        acquisitive_end = cls._anniversary(hiring, period_number) - timedelta(
            days=1
        )
        concessive_start = cls._anniversary(hiring, period_number)
        concessive_end = cls._anniversary(
            hiring, period_number + 1
        ) - timedelta(days=1)
        return (
            acquisitive_start,
            acquisitive_end,
            concessive_start,
            concessive_end,
        )

    def _proportional_days(
        self, period: VacationAccrualPeriod, today: date
    ) -> int:
        total = (period.acquisitive_end - period.acquisitive_start).days + 1
        elapsed = (today - period.acquisitive_start).days + 1
        return int((elapsed / total) * self.VACATION_DAYS_PER_YEAR)

    @staticmethod
    def _is_fully_consumed(period: VacationAccrualPeriod) -> bool:
        consumed = (
            period.days_enjoyed + period.days_double_paid + period.days_sold
        )
        return period.days_reserved == 0 and consumed >= period.days_earned

    def _compute_status(
        self, period: VacationAccrualPeriod, today: date
    ) -> VacationAccrualStatus:
        if today > period.acquisitive_end and self._is_fully_consumed(period):
            return VacationAccrualStatus.CLOSED
        if today > period.concessive_end:
            return VacationAccrualStatus.EXPIRED
        if today > period.acquisitive_end:
            return VacationAccrualStatus.CONCESSIVE
        return VacationAccrualStatus.ACQUISITIVE

    def _sync_period(self, period: VacationAccrualPeriod, today: date) -> None:
        """Atualiza status, elegibilidade para dobro e dias adquiridos."""
        if today > period.acquisitive_end:
            period.days_earned = max(
                period.days_earned, self.VACATION_DAYS_PER_YEAR
            )
        else:
            period.days_earned = max(
                period.days_earned, self._proportional_days(period, today)
            )

        status = self._compute_status(period, today)
        period.status = status
        period.is_double_eligible = (
            status == VacationAccrualStatus.EXPIRED
            and period.available_days > 0
        )

    async def ensure_accrual_periods(
        self, user: User
    ) -> list[VacationAccrualPeriod]:
        """Cria os períodos aquisitivos necessários e sincroniza status."""
        today = date.today()
        result = await self.session.execute(
            select(VacationAccrualPeriod)
            .where(VacationAccrualPeriod.user_id == user.id)
            .order_by(VacationAccrualPeriod.period_number)
        )
        periods = list(result.scalars().all())
        existing = {p.period_number: p for p in periods}

        hiring = user.hiring_date
        if today >= hiring:
            current_number = 1
            while self._anniversary(hiring, current_number) <= today:
                current_number += 1

            for num in range(1, current_number + 1):
                if num in existing:
                    continue
                (
                    acquisitive_start,
                    acquisitive_end,
                    concessive_start,
                    concessive_end,
                ) = self._period_dates(hiring, num)
                period = VacationAccrualPeriod(
                    user_id=user.id,
                    period_number=num,
                    acquisitive_start=acquisitive_start,
                    acquisitive_end=acquisitive_end,
                    concessive_start=concessive_start,
                    concessive_end=concessive_end,
                    status=VacationAccrualStatus.ACQUISITIVE,
                    days_earned=0,
                )
                period.created_by_id = user.id
                self.session.add(period)
                periods.append(period)
                existing[num] = period

        for period in periods:
            self._sync_period(period, today)
        await self.session.flush()
        return periods

    async def get_accrual_periods(
        self, user: User
    ) -> list[VacationAccrualPeriod]:
        await self.ensure_accrual_periods(user)
        result = await self.session.execute(
            select(VacationAccrualPeriod)
            .options(selectinload(VacationAccrualPeriod.grants))
            .where(VacationAccrualPeriod.user_id == user.id)
            .order_by(VacationAccrualPeriod.period_number)
        )
        return list(result.scalars().all())

    async def get_accrual_period(
        self, user: User, period_id: int
    ) -> VacationAccrualPeriod | None:
        await self.ensure_accrual_periods(user)
        result = await self.session.execute(
            select(VacationAccrualPeriod)
            .options(selectinload(VacationAccrualPeriod.grants))
            .where(
                VacationAccrualPeriod.id == period_id,
                VacationAccrualPeriod.user_id == user.id,
            )
        )
        return result.scalar_one_or_none()

    async def _get_target_accrual(
        self, user: User, period_id: Optional[int]
    ) -> VacationAccrualPeriod:
        """Retorna o período alvo (especificado ou o atual em andamento)."""
        if period_id is None:
            periods = await self.ensure_accrual_periods(user)
            target = None
            for period in reversed(periods):
                if period.status in {
                    VacationAccrualStatus.ACQUISITIVE,
                    VacationAccrualStatus.CONCESSIVE,
                }:
                    target = period
                    break
            if target is None:
                target = periods[-1] if periods else None
            if target is None:
                raise ValueError('Nenhum período aquisitivo disponível')
            return target

        result = await self.session.execute(
            select(VacationAccrualPeriod).where(
                VacationAccrualPeriod.id == period_id,
                VacationAccrualPeriod.user_id == user.id,
            )
        )
        period = result.scalar_one_or_none()
        if not period:
            raise ValueError('Período aquisitivo não encontrado')
        self._sync_period(period, date.today())
        return period

    @staticmethod
    def _ensure_requestable(period: VacationAccrualPeriod) -> None:
        if period.status == VacationAccrualStatus.EXPIRED:
            raise ValueError(
                'Período concessivo expirado, não é possível solicitar férias'
            )
        if period.status == VacationAccrualStatus.CLOSED:
            raise ValueError('Período já foi regularizado')

    async def _accrual_has_full_period(
        self, accrual: VacationAccrualPeriod
    ) -> bool:
        result = await self.session.execute(
            select(VacationGrant.id).where(
                VacationGrant.accrual_period_id == accrual.id,
                VacationGrant.days_count >= self.MIN_MAIN_PERIOD_DAYS,
                VacationGrant.status.in_([
                    VacationGrantStatus.GRANTED,
                    VacationGrantStatus.IN_PROGRESS,
                    VacationGrantStatus.FRUITED,
                ]),
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _remaining_split_errors(
        remaining: int, has_full_period: bool
    ) -> list[str]:
        """Valida saldo restante após gozo (permitir período válido)."""
        errors = []
        if remaining <= 0:
            return errors
        if remaining < MIN_PERIOD_DAYS:
            errors.append(
                f'Restariam {remaining} dias após o gozo; '
                f'mínimo para um novo período é {MIN_PERIOD_DAYS} dias'
            )
        elif not has_full_period and remaining < MIN_MAIN_PERIOD_DAYS:
            errors.append(
                f'Sem período de {MIN_MAIN_PERIOD_DAYS} dias ainda; '
                f'restariam {remaining} dias'
            )
        return errors

    # ------------------------------------------------------------------
    # Validação CLT
    # ------------------------------------------------------------------

    def validate_period_dates(self, start: date, end: date) -> list[str]:
        """Valida datas de um período (Art. 134 §3º e §1º CLT)."""
        errors = []

        if self.is_weekend(start) or start.weekday() == self.FRIDAY_WEEKDAY:
            errors.append(
                f'Início ({start.strftime("%d/%m/%Y")}) '
                'não pode ser em sexta, sábado ou domingo '
                '(Art. 134 §3º CLT)'
            )

        if self.is_holiday(start):
            errors.append(
                f'Início ({start.strftime("%d/%m/%Y")}) '
                f'não pode ser em feriado: {self.BRAZIL_HOLIDAYS.get(start)}'
            )

        for days_before in (1, 2):
            check_date = start + timedelta(days=days_before)
            if self.is_holiday(check_date):
                errors.append(
                    f'Início ({start.strftime("%d/%m/%Y")}) '
                    f'não pode ser a {days_before} dia(s) antes de feriado '
                    '(Art. 134 §3º CLT)'
                )
                break

        calendar_days = self.count_calendar_days(start, end)
        if calendar_days < self.MIN_PERIOD_DAYS:
            errors.append(
                f'Período deve ter no mínimo {self.MIN_PERIOD_DAYS} '
                f'dias corridos (tem {calendar_days})'
            )

        return errors

    async def validate_periods_clt(
        self,
        user: User,
        accrual: VacationAccrualPeriod,
        periods: list[VacationPeriodCreate],
    ) -> list[str]:
        errors = []

        if not periods:
            errors.append('Pelo menos um período de férias é obrigatório')
            return errors

        if len(periods) > self.MAX_PERIODS:
            errors.append(
                f'Máximo de {self.MAX_PERIODS} períodos de férias permitidos'
            )

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
            elif (next_start - current_end).days == 1:
                errors.append('Deve haver pelo menos 1 dia entre períodos')

        total_days = sum(
            self.count_calendar_days(p.start_date, p.end_date) for p in periods
        )
        if total_days > accrual.available_days:
            errors.append(
                'Dias solicitados '
                f'({total_days}) excedem saldo disponível '
                f'({accrual.available_days})'
            )

        has_full_period = any(
            self.count_calendar_days(p.start_date, p.end_date)
            >= self.MIN_MAIN_PERIOD_DAYS
            for p in periods
        )
        if not has_full_period:
            has_full_period = await self._accrual_has_full_period(accrual)

        remaining = accrual.available_days - total_days
        errors.extend(self._remaining_split_errors(remaining, has_full_period))

        return errors

    async def preview_vacation(
        self, user: User, data: VacationPreviewRequest
    ) -> VacationPreviewResponse:
        accrual = await self._get_target_accrual(
            user, data.target_accrual_period_id
        )
        errors = await self.validate_periods_clt(user, accrual, data.periods)
        if accrual.status == VacationAccrualStatus.EXPIRED:
            errors.append(
                'Período concessivo expirado, não é possível solicitar férias'
            )

        warnings = []
        total_days = 0
        periods_detail = []

        for i, period in enumerate(data.periods):
            cal_days = self.count_calendar_days(
                period.start_date, period.end_date
            )
            period_type = (
                VacationPeriodType.MAIN
                if cal_days >= self.MIN_MAIN_PERIOD_DAYS
                else VacationPeriodType.COMPLEMENTARY
            )
            periods_detail.append({
                'index': i + 1,
                'start_date': period.start_date.isoformat(),
                'end_date': period.end_date.isoformat(),
                'calendar_days': cal_days,
                'period_type': period_type.value,
            })
            total_days += cal_days

        return VacationPreviewResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            total_days=total_days,
            periods_detail=periods_detail,
        )

    # ------------------------------------------------------------------
    # Requisições
    # ------------------------------------------------------------------

    async def create_request(
        self, user: User, data: VacationRequestCreate
    ) -> VacationRequest:
        accrual = await self._get_target_accrual(
            user, data.target_accrual_period_id
        )
        self._ensure_requestable(accrual)
        errors = await self.validate_periods_clt(user, accrual, data.periods)
        if errors:
            raise ValueError('; '.join(errors))

        request = VacationRequest(
            user_id=user.id,
            target_accrual_period_id=accrual.id,
            status=VacationRequestStatus.SUBMITTED,
            requested_at=datetime.now(),
        )
        request.created_by_id = user.id
        self.session.add(request)
        await self.session.flush()

        for period_data in data.periods:
            cal_days = self.count_calendar_days(
                period_data.start_date, period_data.end_date
            )
            period_type = (
                VacationPeriodType.MAIN
                if cal_days >= self.MIN_MAIN_PERIOD_DAYS
                else VacationPeriodType.COMPLEMENTARY
            )
            period = VacationPeriod(
                request_id=request.id,
                start_date=period_data.start_date,
                end_date=period_data.end_date,
                period_type=period_type,
                days_count=cal_days,
            )
            period.created_by_id = user.id
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

        accrual = request.target_accrual_period
        if accrual.status == VacationAccrualStatus.EXPIRED:
            raise ValueError(
                'Período concessivo expirado, não é possível aprovar'
            )

        total_days = sum(p.days_count for p in request.periods)
        if total_days > accrual.available_days:
            raise ValueError(
                'Saldo insuficiente. Disponível: '
                f'{accrual.available_days}, Solicitado: {total_days}'
            )

        now = datetime.now()
        request.status = VacationRequestStatus.APPROVED
        request.reviewer_id = reviewer.id
        request.reviewed_at = now
        request.reviewer_notes = reviewer_notes

        for period in request.periods:
            grant = VacationGrant(
                user_id=request.user_id,
                accrual_period_id=accrual.id,
                start_date=period.start_date,
                end_date=period.end_date,
                days_count=period.days_count,
                grant_type=VacationGrantType.NORMAL,
                status=VacationGrantStatus.GRANTED,
                approved_by_id=reviewer.id,
                approved_at=now,
            )
            grant.created_by_id = reviewer.id
            self.session.add(grant)
            accrual.days_reserved += period.days_count

        await self.session.flush()
        return request

    async def reject_request(
        self,
        request: VacationRequest,
        reviewer: User,
        reviewer_notes: Optional[str] = None,
    ) -> VacationRequest:
        if request.status not in {
            VacationRequestStatus.SUBMITTED,
            VacationRequestStatus.UNDER_REVIEW,
        }:
            raise ValueError('Solicitação não pode ser rejeitada')

        request.status = VacationRequestStatus.REJECTED
        request.reviewer_id = reviewer.id
        request.reviewed_at = datetime.now()
        request.reviewer_notes = reviewer_notes
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
        await self.session.flush()
        return request

    # ------------------------------------------------------------------
    # Concessões (grants)
    # ------------------------------------------------------------------

    async def create_grant(
        self, data: VacationGrantCreate, creator: User
    ) -> VacationGrant:
        """Admin cadastra gozo retroativo ou pagamento em dobro (Art. 137)."""
        if data.grant_type not in {
            VacationGrantType.RETROACTIVE,
            VacationGrantType.DOUBLE_PAYMENT,
        }:
            raise ValueError(
                'Tipo de concessão inválido; use retroactive ou double_payment'
            )

        result = await self.session.execute(
            select(VacationAccrualPeriod).where(
                VacationAccrualPeriod.id == data.accrual_period_id,
                VacationAccrualPeriod.user_id == data.user_id,
            )
        )
        accrual = result.scalar_one_or_none()
        if not accrual:
            raise ValueError('Período aquisitivo não encontrado')

        self._sync_period(accrual, date.today())
        if accrual.status != VacationAccrualStatus.EXPIRED:
            raise ValueError(
                'Apenas períodos com concessivo expirado aceitam '
                'gozo retroativo ou pagamento em dobro'
            )

        days = self.count_calendar_days(data.start_date, data.end_date)
        if days < 1:
            raise ValueError('Período inválido')
        if data.grant_type == VacationGrantType.RETROACTIVE:
            if days < self.MIN_PERIOD_DAYS:
                raise ValueError(
                    f'Mínimo de {self.MIN_PERIOD_DAYS} dias corridos para gozo'
                )
        if days > accrual.available_days:
            raise ValueError(
                f'Dias ({days}) excedem saldo disponível '
                f'({accrual.available_days})'
            )

        now = datetime.now()
        if data.grant_type == VacationGrantType.DOUBLE_PAYMENT:
            status = VacationGrantStatus.PAID_DOUBLE
        else:
            status = VacationGrantStatus.FRUITED
        grant = VacationGrant(
            user_id=data.user_id,
            accrual_period_id=accrual.id,
            start_date=data.start_date,
            end_date=data.end_date,
            days_count=days,
            grant_type=data.grant_type,
            status=status,
            approved_by_id=creator.id,
            approved_at=now,
            confirmed_by_id=creator.id,
            confirmed_at=now,
            notes=data.notes,
        )
        grant.created_by_id = creator.id
        self.session.add(grant)
        if data.grant_type == VacationGrantType.DOUBLE_PAYMENT:
            accrual.days_double_paid += days
        else:
            accrual.days_enjoyed += days
        self._sync_period(accrual, date.today())
        await self.session.flush()
        return grant

    async def get_grant(self, grant_id: int) -> VacationGrant | None:
        result = await self.session.execute(
            select(VacationGrant).where(VacationGrant.id == grant_id)
        )
        return result.scalar_one_or_none()

    async def list_grants(
        self,
        user_id: Optional[int] = None,
        status: Optional[VacationGrantStatus] = None,
        accrual_period_id: Optional[int] = None,
        setor: Optional[Setor] = None,
        subsetor: Optional[str] = None,
    ) -> list[VacationGrant]:
        query = select(VacationGrant)
        if user_id is not None:
            query = query.where(VacationGrant.user_id == user_id)
        if status is not None:
            query = query.where(VacationGrant.status == status)
        if accrual_period_id is not None:
            query = query.where(
                VacationGrant.accrual_period_id == accrual_period_id
            )
        if setor is not None or subsetor is not None:
            query = query.join(User, VacationGrant.user_id == User.id)
            if setor is not None:
                query = query.where(User.setor == setor)
            if subsetor is not None:
                query = query.where(User.subsetor == subsetor)
        query = query.order_by(VacationGrant.start_date.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def confirm_fruition(
        self,
        grant: VacationGrant,
        confirming_user: User,
        confirm: bool,
        notes: Optional[str] = None,
    ) -> VacationGrant:
        """RH confirma (ou não) a fruição efetiva de uma concessão."""
        if grant.status not in {
            VacationGrantStatus.GRANTED,
            VacationGrantStatus.IN_PROGRESS,
        }:
            raise ValueError('Concessão não está pendente de confirmação')

        accrual = grant.accrual_period
        if confirm:
            if grant.grant_type == VacationGrantType.DOUBLE_PAYMENT:
                grant.status = VacationGrantStatus.PAID_DOUBLE
                accrual.days_double_paid += grant.days_count
            else:
                grant.status = VacationGrantStatus.FRUITED
                accrual.days_enjoyed += grant.days_count
            accrual.days_reserved -= grant.days_count
        else:
            grant.status = VacationGrantStatus.CANCELLED
            accrual.days_reserved -= grant.days_count

        grant.confirmed_by_id = confirming_user.id
        grant.confirmed_at = datetime.now()
        if notes is not None:
            grant.notes = notes

        self._sync_period(accrual, date.today())
        await self.session.flush()
        return grant

    async def sell_days(
        self,
        accrual: VacationAccrualPeriod,
        days: int,
        admin: User,
    ) -> VacationAccrualPeriod:
        """Venda de dias (abono pecuniário) - apenas RH/admin."""
        self._sync_period(accrual, date.today())
        if accrual.status == VacationAccrualStatus.EXPIRED:
            raise ValueError(
                'Período concessivo expirado, não é possível vender dias'
            )
        if days > self.MAX_SELL_DAYS:
            raise ValueError(
                f'Máximo {self.MAX_SELL_DAYS} dias vendidos '
                'por período aquisitivo'
            )
        if days > accrual.available_days:
            raise ValueError(
                f'Apenas {accrual.available_days} dias disponíveis para venda'
            )

        remaining = accrual.available_days - days
        has_full_period = await self._accrual_has_full_period(accrual)
        split_errors = self._remaining_split_errors(remaining, has_full_period)
        if split_errors:
            raise ValueError('; '.join(split_errors))

        accrual.days_sold += days
        accrual.updated_by_id = admin.id
        self._sync_period(accrual, date.today())
        await self.session.flush()
        return accrual

    @staticmethod
    def _has_active_schedule(period: VacationAccrualPeriod) -> bool:
        """Há férias já marcadas (concessão ativa) ou solicitadas."""
        for grant in period.grants:
            if grant.status in {
                VacationGrantStatus.GRANTED,
                VacationGrantStatus.IN_PROGRESS,
            }:
                return True
        for request in period.requests:
            if request.status in {
                VacationRequestStatus.SUBMITTED,
                VacationRequestStatus.UNDER_REVIEW,
                VacationRequestStatus.APPROVED,
            }:
                return True
        return False

    async def get_vacation_alerts(self) -> list[dict]:
        """Alertas de férias por período concessivo.

        Inclui períodos com aquisição completa que precisam de atenção:
        - Vencidos (concessivo já expirou) com saldo a regularizar;
        - Prestes a vencer (concessivo vence em até 30 dias) sem férias
          marcadas;
        - Em aberto sem férias marcadas ou solicitadas (basta marcar).
        """
        today = date.today()
        result = await self.session.execute(
            select(VacationAccrualPeriod)
            .options(
                selectinload(VacationAccrualPeriod.user),
                selectinload(VacationAccrualPeriod.grants),
                selectinload(VacationAccrualPeriod.requests),
            )
            .where(VacationAccrualPeriod.acquisitive_end < today)
            .order_by(VacationAccrualPeriod.concessive_end)
        )
        alerts = []
        for period in result.scalars().all():
            self._sync_period(period, today)
            if period.status == VacationAccrualStatus.ACQUISITIVE:
                continue
            if period.available_days <= 0:
                continue

            if period.status == VacationAccrualStatus.EXPIRED:
                alert_type = VacationAlertType.EXPIRED
            else:
                if self._has_active_schedule(period):
                    continue
                days_until_expiry = (period.concessive_end - today).days
                alert_type = (
                    VacationAlertType.ABOUT_TO_EXPIRE
                    if days_until_expiry <= ALERT_DAYS_WINDOW
                    else VacationAlertType.PENDING
                )

            alerts.append({
                'id': period.id,
                'user_id': period.user_id,
                'user_name': (
                    period.user.name if period.user else 'Desconhecido'
                ),
                'period_number': period.period_number,
                'acquisitive_start': period.acquisitive_start,
                'acquisitive_end': period.acquisitive_end,
                'concessive_start': period.concessive_start,
                'concessive_end': period.concessive_end,
                'remaining_days': period.available_days,
                'alert_type': alert_type,
            })
        if alerts:
            await self.session.flush()
        return alerts
