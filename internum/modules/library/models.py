from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internum.core.models.mixins import AuditMixin
from internum.core.models.registry import table_registry
from internum.modules.library.enums import LoanStatus

# ruff: noqa: F821


@table_registry.mapped_as_dataclass
class Book(AuditMixin):
    __tablename__ = 'books'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    isbn: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(Text, nullable=False)
    publisher: Mapped[str] = mapped_column(Text, nullable=False)
    edition: Mapped[int]
    year: Mapped[int]
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    available_quantity: Mapped[int] = mapped_column(nullable=False, default=1)

    loans: Mapped[list['Loan']] = relationship(
        back_populates='book', init=False
    )

    def lend(self):
        if self.available_quantity <= 0:
            raise ValueError('Book not available for lending.')
        self.available_quantity -= 1

    def return_book(self):
        if self.available_quantity >= self.quantity:
            raise ValueError('Available quantity already at maximum.')
        self.available_quantity += 1


@table_registry.mapped_as_dataclass
class Loan(AuditMixin):
    __tablename__ = 'loans'

    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    book_id: Mapped[int] = mapped_column(ForeignKey('books.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    approved_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('users.id'),
        default=None,
    )

    loan_period_days: Mapped[int] = mapped_column(default=14)

    borrowed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, init=False
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, init=False
    )
    returned_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, init=False
    )

    status: Mapped[LoanStatus] = mapped_column(
        SqlEnum(LoanStatus),
        default=LoanStatus.REQUESTED,
    )

    user: Mapped['User'] = relationship(
        'User', foreign_keys=[user_id], lazy='joined', init=False
    )

    approved_by: Mapped[Optional['User']] = relationship(
        'User', foreign_keys=[approved_by_id], lazy='joined', init=False
    )

    book: Mapped['Book'] = relationship(back_populates='loans', init=False)

    def mark_as_cancelled(self, approver: 'User'):
        if self.status not in {LoanStatus.REQUESTED}:
            raise ValueError('Loan is not currently pendind approve.')
        self.status = LoanStatus.CANCELLED
        self.book.return_book()

    def approve_and_start(self, approver: 'User'):
        if self.status != LoanStatus.REQUESTED:
            raise ValueError('Only requested loans can be started.')
        self.status = LoanStatus.BORROWED
        self.approved_by = approver
        self.borrowed_at = datetime.utcnow()
        self.due_date = datetime.utcnow() + timedelta(
            days=self.loan_period_days
        )

    def reject(self, approver: 'User'):
        if self.status != LoanStatus.REQUESTED:
            raise ValueError('Only requested loans can be rejected.')
        self.status = LoanStatus.REJECTED
        self.approved_by = approver

    def mark_as_returned(self):
        if self.status not in {LoanStatus.BORROWED, LoanStatus.LATE}:
            raise ValueError('Loan is not currently borrowed.')
        self.returned_at = datetime.utcnow()
        self.status = LoanStatus.RETURNED
        self.book.return_book()

    def check_overdue(self):
        if (
            self.status == LoanStatus.BORROWED
            and self.due_date
            and self.due_date < datetime.utcnow()
        ):
            self.status = LoanStatus.LATE
