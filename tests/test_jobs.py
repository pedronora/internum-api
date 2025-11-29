from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from internum.modules.auth.jobs import (
    _delete_expired_reset_tokens,  # noqa: PLC2701
)
from internum.modules.auth.models import PasswordResetToken
from internum.modules.library.jobs import _mark_overdue_loans  # noqa: PLC2701
from internum.modules.library.models import Book, Loan, LoanStatus


@pytest.mark.asyncio
async def test_delete_expired_tokens(session, user):
    expected_remain_tokens = 2

    expired_token = PasswordResetToken(
        user_id=user.id,
        token='expired_token',
        expires_at=datetime.now(UTC) - timedelta(days=1),
        used=False,
    )

    used_token = PasswordResetToken(
        user_id=user.id,
        token='used_token',
        expires_at=datetime.now(UTC) + timedelta(days=1),
        used=True,
    )

    valid_token = PasswordResetToken(
        user_id=user.id,
        token='valid_token',
        expires_at=datetime.now(UTC) + timedelta(days=1),
        used=False,
    )

    session.add_all([expired_token, used_token, valid_token])
    await session.commit()

    await _delete_expired_reset_tokens(session)

    remaining_tokens = await session.scalars(select(PasswordResetToken))
    remaining_tokens_list = remaining_tokens.all()

    assert len(remaining_tokens_list) == expected_remain_tokens
    assert remaining_tokens_list[0].token in {'valid_token', 'used_token'}


@pytest.mark.asyncio
async def test_delete_expired_tokens_no_tokens_to_delete(session):
    await _delete_expired_reset_tokens(session)

    remaining_tokens = await session.scalars(select(PasswordResetToken))
    assert len(remaining_tokens.all()) == 0


@pytest.mark.asyncio
async def test_delete_expired_tokens_only_expired(session, user):
    expired_token = PasswordResetToken(
        user_id=user.id,
        token='expired_only',
        expires_at=datetime.now(UTC) - timedelta(hours=1),
        used=False,
    )

    session.add(expired_token)
    await session.commit()

    await _delete_expired_reset_tokens(session)

    remaining_tokens = await session.scalars(select(PasswordResetToken))
    assert len(remaining_tokens.all()) == 0


@pytest.mark.asyncio
async def test_delete_expired_tokens_only_used(session, user):
    used_token = PasswordResetToken(
        user_id=user.id,
        token='used_only',
        expires_at=datetime.now(UTC) + timedelta(days=1),
        used=True,
    )

    session.add(used_token)
    await session.commit()

    await _delete_expired_reset_tokens(session)

    remaining_tokens = await session.scalars(select(PasswordResetToken))
    assert len(remaining_tokens.all()) == 1


@pytest.mark.asyncio
async def test_check_overdue_loans_marks_overdue(
    session, mock_email_service, user, user_admin
):
    book = Book(
        isbn='123',
        title='Book',
        author='Author',
        publisher='Publisher',
        edition=1,
        year=2020,
        quantity=1,
        available_quantity=0,
    )
    book.created_by_id = user_admin.id
    session.add(book)
    await session.commit()
    await session.refresh(book)

    overdue_loan = Loan(
        book_id=book.id,
        status=LoanStatus.BORROWED,
    )

    overdue_loan.created_by_id = user.id

    overdue_loan.borrowed_at = datetime.now(timezone.utc) - timedelta(days=10)
    overdue_loan.due_date = datetime.now(timezone.utc) - timedelta(days=3)

    session.add(overdue_loan)
    await session.commit()
    await session.refresh(overdue_loan)

    await _mark_overdue_loans(session)

    await session.refresh(overdue_loan)

    assert overdue_loan.status == LoanStatus.LATE
    assert overdue_loan.due_date is not None
    assert mock_email_service.call_count == 1


@pytest.mark.asyncio
async def test_check_overdue_loans_ignores_not_due(
    session, mock_email_service, user, user_admin
):
    book = Book(
        isbn='12345',
        title='Valid',
        author='Author',
        publisher='Pub',
        edition=1,
        year=2021,
        quantity=1,
        available_quantity=0,
    )
    book.created_by_id = user_admin.id
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan = Loan(
        book_id=book.id,
        status=LoanStatus.BORROWED,
    )
    loan.created_by_id = user.id
    loan.due_date = datetime.now(timezone.utc) + timedelta(days=5)
    loan.borrowed_at = datetime.now(timezone.utc) - timedelta(days=1)
    session.add(loan)

    await session.commit()
    await session.refresh(loan)

    await _mark_overdue_loans(session)

    await session.refresh(loan)
    assert loan.status == LoanStatus.BORROWED
    assert mock_email_service.call_count == 0
