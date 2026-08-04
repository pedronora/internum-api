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
    VacationPeriodType,
    VacationRequestStatus,
    VacationStatus,
)

if TYPE_CHECKING:
    from internum.modules.users.models import User


@table_registry.mapped_as_dataclass
class VacationBalance(AuditMixin):
    __tablename__ = 'vacation_balances'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True
    )

    current_period_start: Mapped[date] = mapped_column(Date, nullable=False)
    current_period_end: Mapped[date] = mapped_column(Date, nullable=False)

    accrued_days: Mapped[int] = mapped_column(Integer, default=0)
    proportional_days: Mapped[int] = mapped_column(Integer, default=0)
    enjoyed_days: Mapped[int] = mapped_column(Integer, default=0)
    sold_days: Mapped[int] = mapped_column(Integer, default=0)

    # Ajuste manual para migração/histórico pré-existente
    manual_adjustment_days: Mapped[int] = mapped_column(Integer, default=0)
    adjustment_reason: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, default=None
    )
    adjusted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    adjusted_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )

    next_period_start: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, default=None
    )
    next_period_end: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True, default=None
    )
    next_accrued_days: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped['User'] = relationship(
        'User',
        foreign_keys='VacationBalance.user_id',
        backref='vacation_balance',
        lazy='joined',
        init=False,
    )
    adjusted_by: Mapped[Optional['User']] = relationship(
        'User',
        foreign_keys='VacationBalance.adjusted_by_id',
        lazy='joined',
        init=False,
    )

    @property
    def available_days(self) -> int:
        return (
            self.accrued_days
            + self.proportional_days
            + self.manual_adjustment_days
            - self.enjoyed_days
            - self.sold_days
        )

    @property
    def total_earned(self) -> int:
        return self.accrued_days + self.proportional_days


@table_registry.mapped_as_dataclass
class VacationRequest(AuditMixin):
    __tablename__ = 'vacation_requests'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False
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
        foreign_keys=[user_id],
        backref='vacation_requests',
        lazy='joined',
        init=False,
    )
    reviewer: Mapped[Optional['User']] = relationship(
        'User',
        foreign_keys=[reviewer_id],
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
        default=VacationPeriodType.FULL,
        nullable=False,
    )

    status: Mapped[VacationStatus] = mapped_column(
        SqlEnum(VacationStatus, name='vacation_status_enum'),
        default=VacationStatus.PENDING,
        nullable=False,
    )

    days_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    working_days_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    request: Mapped['VacationRequest'] = relationship(
        'VacationRequest', back_populates='periods', lazy='joined', init=False
    )

    __table_args__ = (
        UniqueConstraint(
            'request_id', 'start_date', name='uq_period_request_start'
        ),
    )

    @property
    def is_approved(self) -> bool:
        return self.status == VacationStatus.APPROVED
