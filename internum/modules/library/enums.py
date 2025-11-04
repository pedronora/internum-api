import enum


class LoanStatus(str, enum.Enum):
    REQUESTED = 'requested'
    BORROWED = 'borrowed'
    RETURNED = 'returned'
    LATE = 'late'
    REJECTED = 'rejected'
