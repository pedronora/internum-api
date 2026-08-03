from enum import Enum


class VacationStatus(str, Enum):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
    ENJOYED = 'enjoyed'


class VacationPeriodType(str, Enum):
    FULL = 'full'
    PROPORTIONAL = 'proportional'


class VacationRequestStatus(str, Enum):
    DRAFT = 'draft'
    SUBMITTED = 'submitted'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    CANCELLED = 'cancelled'
