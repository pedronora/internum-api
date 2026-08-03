from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from internum.modules.vacation.enums import (
    VacationPeriodType,
    VacationRequestStatus,
    VacationStatus,
)

MAX_PERIODS = 3
MAX_SELL_DAYS = 10


class VacationPeriodBase(BaseModel):
    start_date: date
    end_date: date
    period_type: VacationPeriodType = VacationPeriodType.FULL

    @field_validator('end_date')
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        if 'start_date' in info.data and v < info.data['start_date']:
            raise ValueError('Data de fim deve ser posterior à data de início')
        return v


class VacationPeriodCreate(VacationPeriodBase):
    pass


class VacationPeriodUpdate(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    period_type: Optional[VacationPeriodType] = None

    @model_validator(mode='after')
    def check_dates(self) -> 'VacationPeriodUpdate':
        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            raise ValueError('Data de fim deve ser posterior à data de início')
        return self


class VacationPeriodRead(VacationPeriodBase):
    id: int
    status: VacationStatus
    days_count: int
    working_days_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VacationRequestBase(BaseModel):
    pass


class VacationRequestCreate(BaseModel):
    periods: list[VacationPeriodCreate] = Field(min_length=1, max_length=3)

    @model_validator(mode='after')
    def validate_periods(self) -> 'VacationRequestCreate':
        if len(self.periods) > MAX_PERIODS:
            raise ValueError('Máximo de 3 períodos de férias')
        return self


class VacationRequestUpdate(BaseModel):
    periods: Optional[list[VacationPeriodUpdate]] = None
    reviewer_notes: Optional[str] = None


class VacationRequestRead(VacationRequestBase):
    id: int
    user_id: int
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
    status: VacationRequestStatus
    requested_at: Optional[datetime] = None
    total_days: int
    periods_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class VacationBalanceRead(BaseModel):
    id: int
    user_id: int
    current_period_start: date
    current_period_end: date
    accrued_days: int
    proportional_days: int
    enjoyed_days: int
    sold_days: int
    manual_adjustment_days: int
    adjustment_reason: Optional[str] = None
    adjusted_at: Optional[datetime] = None
    adjusted_by_id: Optional[int] = None
    available_days: int
    next_period_start: Optional[date] = None
    next_period_end: Optional[date] = None
    next_accrued_days: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class VacationPreviewRequest(BaseModel):
    periods: list[VacationPeriodCreate] = Field(min_length=1, max_length=3)

    @model_validator(mode='after')
    def validate_periods(self) -> 'VacationPreviewRequest':
        if len(self.periods) > MAX_PERIODS:
            raise ValueError('Máximo de 3 períodos de férias')
        return self


class VacationPreviewResponse(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
    total_days: int
    total_working_days: int
    periods_detail: list[dict] = []


class VacationApprovalRequest(BaseModel):
    action: str = Field(pattern='^(approve|reject)$')
    reviewer_notes: Optional[str] = None
    periods: Optional[list[VacationPeriodUpdate]] = None


class VacationSellDaysRequest(BaseModel):
    days: int = Field(ge=1, le=MAX_SELL_DAYS)

    @field_validator('days')
    @classmethod
    def validate_sell_days(cls, v: int) -> int:
        if v > MAX_SELL_DAYS:
            raise ValueError(
                'Máximo 10 dias podem ser vendidos por período aquisitivo'
            )
        return v


class VacationBalanceAdjustRequest(BaseModel):
    manual_adjustment_days: int
    adjustment_reason: str = Field(min_length=5, max_length=500)
