from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from internum.modules.vacation.enums import (
    VacationAccrualStatus,
    VacationAlertType,
    VacationGrantStatus,
    VacationGrantType,
    VacationPeriodType,
    VacationRequestStatus,
)

if TYPE_CHECKING:
    from internum.modules.vacation.schemas import (
        VacationAccrualPeriodRead,
        VacationGrantRead,
    )

MAX_PERIODS = 3
VACATION_DAYS_PER_YEAR = 30
MIN_PERIOD_DAYS = 5
MIN_MAIN_PERIOD_DAYS = 14
MAX_SELL_DAYS = 10


class VacationPeriodBase(BaseModel):
    start_date: date
    end_date: date

    @field_validator('end_date')
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start_date = info.data.get('start_date')
        if start_date and v < start_date:
            raise ValueError('Data de fim deve ser posterior à data de início')
        return v


class VacationPeriodCreate(VacationPeriodBase):
    pass


class VacationPeriodRead(VacationPeriodBase):
    id: int
    period_type: VacationPeriodType
    days_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VacationRequestCreate(BaseModel):
    target_accrual_period_id: int
    periods: list[VacationPeriodCreate] = Field(
        min_length=1, max_length=MAX_PERIODS
    )

    @model_validator(mode='after')
    def validate_periods(self) -> 'VacationRequestCreate':
        if len(self.periods) > MAX_PERIODS:
            raise ValueError(f'Máximo de {MAX_PERIODS} períodos de férias')
        return self


class VacationRequestRead(BaseModel):
    id: int
    user_id: int
    target_accrual_period_id: int
    reviewer_id: Optional[int] = None
    status: VacationRequestStatus
    requested_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewer_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    periods: list[VacationPeriodRead] = []
    user_name: Optional[str] = None
    reviewer_name: Optional[str] = None

    class Config:
        from_attributes = True


class VacationRequestListItem(BaseModel):
    id: int
    user_id: int
    user_name: str
    target_accrual_period_id: int
    status: VacationRequestStatus
    requested_at: Optional[datetime] = None
    total_days: int
    periods_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class VacationAccrualPeriodRead(BaseModel):
    id: int
    user_id: int
    period_number: int
    acquisitive_start: date
    acquisitive_end: date
    concessive_start: date
    concessive_end: date
    status: VacationAccrualStatus
    days_earned: int
    days_reserved: int
    days_enjoyed: int
    days_sold: int
    days_double_paid: int
    is_double_eligible: bool
    available_days: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    grants: list['VacationGrantRead'] = []

    class Config:
        from_attributes = True


class VacationGrantBase(BaseModel):
    user_id: int
    accrual_period_id: int
    start_date: date
    end_date: date
    grant_type: VacationGrantType
    notes: Optional[str] = None


class VacationGrantCreate(VacationGrantBase):
    pass


class VacationGrantAdminCreate(BaseModel):
    start_date: date
    end_date: date
    grant_type: VacationGrantType
    notes: Optional[str] = None


class VacationGrantRead(VacationGrantBase):
    id: int
    days_count: int
    status: VacationGrantStatus
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    confirmed_by_id: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    is_regularization: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    user_name: Optional[str] = None
    approved_by_name: Optional[str] = None
    confirmed_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class VacationPreviewRequest(BaseModel):
    target_accrual_period_id: Optional[int] = None
    periods: list[VacationPeriodCreate] = Field(
        min_length=1, max_length=MAX_PERIODS
    )

    @model_validator(mode='after')
    def validate_periods(self) -> 'VacationPreviewRequest':
        if len(self.periods) > MAX_PERIODS:
            raise ValueError(f'Máximo de {MAX_PERIODS} períodos de férias')
        return self


class VacationPreviewResponse(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    total_days: int
    periods_detail: list[dict] = []


class VacationReviewRequest(BaseModel):
    reviewer_notes: Optional[str] = None


class VacationSellDaysRequest(BaseModel):
    days: int = Field(ge=1, le=MAX_SELL_DAYS)

    @field_validator('days')
    @classmethod
    def validate_sell_days(cls, v: int) -> int:
        if v > MAX_SELL_DAYS:
            raise ValueError(
                'Máximo '
                f'{MAX_SELL_DAYS} dias podem ser vendidos '
                'por período aquisitivo'
            )
        return v


class VacationConfirmFruitionRequest(BaseModel):
    confirm: bool
    notes: Optional[str] = None


class VacationAccrualPeriodAlert(BaseModel):
    id: int
    user_id: int
    user_name: str
    period_number: int
    acquisitive_start: date
    acquisitive_end: date
    concessive_start: date
    concessive_end: date
    remaining_days: int
    alert_type: VacationAlertType
