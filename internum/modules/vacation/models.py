from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internum.core.models.mixins import AuditMixin
from internum.core.models.registry import table_registry
from internum.modules.vacation.enums import (
    VacationAccrualStatus,
    VacationGrantStatus,
    VacationGrantType,
    VacationPeriodType,
    VacationRequestStatus,
)

if TYPE_CHECKING:
    from internum.modules.users.models import User


@table_registry.mapped_as_dataclass
class VacationAccrualPeriod(AuditMixin):
    __tablename__ = 'vacation_accrual_periods'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )

    period_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Período aquisitivo (trabalhou)
    acquisitive_start: Mapped[date] = mapped_column(Date, nullable=False)
    acquisitive_end: Mapped[date] = mapped_column(Date, nullable=False)

    # Período concessivo (pode gozar)
    concessive_start: Mapped[date] = mapped_column(Date, nullable=False)
    concessive_end: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[VacationAccrualStatus] = mapped_column(
        SqlEnum(VacationAccrualStatus, name='vacation_accrual_status_enum'),
        default=VacationAccrualStatus.ACQUISITIVE,
        nullable=False,
    )

    # Direitos e contadores (dias corridos)
    days_earned: Mapped[int] = mapped_column(Integer, default=30)
    days_reserved: Mapped[int] = mapped_column(Integer, default=0)
    days_enjoyed: Mapped[int] = mapped_column(Integer, default=0)
    days_sold: Mapped[int] = mapped_column(Integer, default=0)
    days_double_paid: Mapped[int] = mapped_column(Integer, default=0)

    # Se período concessivo expirou sem fruição
    is_double_eligible: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )

    user: Mapped['User'] = relationship(
        'User',
        foreign_keys='VacationAccrualPeriod.user_id',
        backref='vacation_accrual_periods',
        lazy='selectin',
        init=False,
    )

    __table_args__ = (
        UniqueConstraint(
            'user_id', 'period_number', name='uq_accrual_user_period'
        ),
    )

    @property
    def available_days(self) -> int:
        """Saldo disponível para gozo/reserva."""
        return (
            self.days_earned
            - self.days_reserved
            - self.days_enjoyed
            - self.days_sold
            - self.days_double_paid
        )

    @property
    def is_expired(self) -> bool:
        return self.status == VacationAccrualStatus.EXPIRED


@table_registry.mapped_as_dataclass
class VacationGrant(AuditMixin):
    __tablename__ = 'vacation_grants'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    accrual_period_id: Mapped[int] = mapped_column(
        ForeignKey('vacation_accrual_periods.id', ondelete='CASCADE'),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_count: Mapped[int] = mapped_column(Integer, nullable=False)

    grant_type: Mapped[VacationGrantType] = mapped_column(
        SqlEnum(VacationGrantType, name='vacation_grant_type_enum'),
        default=VacationGrantType.NORMAL,
        nullable=False,
    )

    status: Mapped[VacationGrantStatus] = mapped_column(
        SqlEnum(VacationGrantStatus, name='vacation_grant_status_enum'),
        default=VacationGrantStatus.GRANTED,
        nullable=False,
    )

    approved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    confirmed_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default=None
    )

    user: Mapped['User'] = relationship(
        'User',
        foreign_keys='VacationGrant.user_id',
        backref='vacation_grants',
        lazy='joined',
        init=False,
    )
    accrual_period: Mapped['VacationAccrualPeriod'] = relationship(
        'VacationAccrualPeriod',
        foreign_keys='VacationGrant.accrual_period_id',
        backref='grants',
        lazy='joined',
        init=False,
    )
    approved_by: Mapped[Optional['User']] = relationship(
        'User',
        foreign_keys='VacationGrant.approved_by_id',
        lazy='joined',
        init=False,
    )
    confirmed_by: Mapped[Optional['User']] = relationship(
        'User',
        foreign_keys='VacationGrant.confirmed_by_id',
        lazy='joined',
        init=False,
    )

    @property
    def is_regularization(self) -> bool:
        return self.grant_type in {
            VacationGrantType.RETROACTIVE,
            VacationGrantType.DOUBLE_PAYMENT,
        }


@table_registry.mapped_as_dataclass
class VacationRequest(AuditMixin):
    __tablename__ = 'vacation_requests'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    target_accrual_period_id: Mapped[int] = mapped_column(
        ForeignKey('vacation_accrual_periods.id', ondelete='CASCADE'),
        nullable=False,
    )
    reviewer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )

    status: Mapped[VacationRequestStatus] = mapped_column(
        SqlEnum(VacationRequestStatus, name='vacation_request_status_enum'),
        default=VacationRequestStatus.DRAFT,
        nullable=False,
    )

    requested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    reviewer_notes: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default=None
    )

    user: Mapped['User'] = relationship(
        'User',
        foreign_keys='VacationRequest.user_id',
        backref='vacation_requests',
        lazy='joined',
        init=False,
    )
    target_accrual_period: Mapped['VacationAccrualPeriod'] = relationship(
        'VacationAccrualPeriod',
        foreign_keys='VacationRequest.target_accrual_period_id',
        backref='requests',
        lazy='joined',
        init=False,
    )
    reviewer: Mapped[Optional['User']] = relationship(
        'User',
        foreign_keys='VacationRequest.reviewer_id',
        backref='reviewed_vacation_requests',
        lazy='joined',
        init=False,
    )
    periods: Mapped[list['VacationPeriod']] = relationship(
        'VacationPeriod',
        back_populates='request',
        cascade='all, delete-orphan',
        lazy='selectin',
        init=False,
    )


@table_registry.mapped_as_dataclass
class VacationPeriod(AuditMixin):
    __tablename__ = 'vacation_periods'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey('vacation_requests.id', ondelete='CASCADE'), nullable=False
    )

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[VacationPeriodType] = mapped_column(
        SqlEnum(VacationPeriodType, name='vacation_period_type_enum'),
        default=VacationPeriodType.MAIN,
        nullable=False,
    )

    days_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    request: Mapped['VacationRequest'] = relationship(
        'VacationRequest', back_populates='periods', lazy='joined', init=False
    )

    __table_args__ = (
        UniqueConstraint(
            'request_id', 'start_date', name='uq_period_request_start'
        ),
    )
