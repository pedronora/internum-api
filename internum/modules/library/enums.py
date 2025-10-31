import enum


class LoanStatus(str, enum.Enum):
    REQUESTED = 'requested'
    APPROVED = 'approved'
    BORROWED = 'borrowed'
    RETURNED = 'returned'
    LATE = 'late'
