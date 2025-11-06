from enum import Enum


class LoanStatus(str, Enum):
    REQUESTED = 'requested'
    BORROWED = 'borrowed'
    RETURNED = 'returned'
    LATE = 'late'
    REJECTED = 'rejected'
    CANCELED = 'canceled'
