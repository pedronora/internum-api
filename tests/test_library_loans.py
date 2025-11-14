from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from unittest.mock import patch

import factory
import pytest

from internum.modules.library.models import Book, Loan, LoanStatus

ENDPOINT_URL = '/api/v1/library/loans'


class BookFactory(factory.Factory):
    class Meta:
        model = Book

    isbn = factory.Faker('isbn13')
    title = factory.Faker('sentence', nb_words=3)
    author = factory.Faker('name')
    publisher = factory.Faker('company')
    edition = factory.Faker('pyint', min_value=1, max_value=10)
    year = factory.Faker('year')
    quantity = 1
    available_quantity = 1


@pytest.mark.asyncio
async def test_loan_flow_success(
    session, client, token, token_admin, user, mock_email_service
):
    total_emails = 0

    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    resp = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == HTTPStatus.CREATED
    loan = resp.json()
    assert loan['status'] == LoanStatus.REQUESTED

    loan_id = loan['id']

    total_emails += 1
    assert mock_email_service.call_count == total_emails

    resp = client.patch(
        f'{ENDPOINT_URL}/{loan_id}/approve',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.BORROWED

    total_emails += 1
    assert mock_email_service.call_count == total_emails

    resp = client.patch(
        f'{ENDPOINT_URL}/{loan_id}/return',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.RETURNED

    total_emails += 1
    assert mock_email_service.call_count == total_emails


@pytest.mark.asyncio
async def test_loan_flow_cancel_by_user(
    session, client, token, user, mock_email_service
):
    total_emails = 0

    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    resp = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )
    loan_id = resp.json()['id']

    total_emails += 1
    assert mock_email_service.call_count == total_emails

    resp = client.patch(
        f'{ENDPOINT_URL}/{loan_id}/cancel',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.CANCELED
    total_emails += 1
    assert mock_email_service.call_count == total_emails


@pytest.mark.asyncio
async def test_loan_flow_reject_by_admin(
    session, client, token, token_admin, user, mock_email_service
):
    total_emails = 0

    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    resp = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )
    loan_id = resp.json()['id']

    total_emails += 1
    assert mock_email_service.call_count == total_emails

    resp = client.patch(
        f'{ENDPOINT_URL}/{loan_id}/reject',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.REJECTED
    total_emails += 1
    assert mock_email_service.call_count == total_emails


@pytest.mark.asyncio
async def test_request_loan_unavailable_book(
    session, client, user, token, mock_email_service
):
    book = BookFactory(quantity=1, available_quantity=0)
    book.created_by_id = user.id
    session.add(book)
    await session.commit()
    await session.refresh(book)

    response = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert 'not available' in response.json()['detail'].lower()

    assert mock_email_service.call_count == 0


@pytest.mark.asyncio
async def test_list_loans_admin_success(session, client, user, token_admin):
    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan = Loan(book_id=book.id, user_id=user.id)
    session.add(loan)
    await session.commit()

    response = client.get(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert 'meta' in data
    assert len(data['loans']) >= 1


@pytest.mark.asyncio
async def test_list_my_loans_success(session, client, user, token):
    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan = Loan(book_id=book.id, user_id=user.id)
    session.add(loan)
    await session.commit()

    response = client.get(
        f'{ENDPOINT_URL}/my',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert 'meta' in data
    assert all(
        loan_item.get('user', {}).get('id') == user.id
        for loan_item in data['loans']
    )


def _dt(days):
    return datetime.now(timezone.utc) + timedelta(days=days)


@pytest.mark.asyncio
async def test_check_overdue_updates_status():
    loan = Loan(
        book_id=1,
        user_id=1,
    )
    loan.status = LoanStatus.BORROWED
    loan.borrowed_at = _dt(-10)
    loan.due_date = _dt(-2)

    loan.check_overdue()

    assert loan.status == LoanStatus.LATE


@pytest.mark.asyncio
async def test_check_overdue_ignores_not_due():
    loan = Loan(
        book_id=1,
        user_id=1,
    )
    loan.status = LoanStatus.BORROWED
    loan.borrowed_at = _dt(-2)
    loan.due_date = _dt(+5)

    loan.check_overdue()

    assert loan.status == LoanStatus.BORROWED


@pytest.mark.asyncio
async def test_check_overdue_ignores_non_borrowed():
    for invalid in [
        LoanStatus.REQUESTED,
        LoanStatus.REJECTED,
        LoanStatus.CANCELED,
        LoanStatus.RETURNED,
        LoanStatus.LATE,
    ]:
        loan = Loan(book_id=1, user_id=1, status=invalid)

        loan.check_overdue()

        assert loan.status == invalid
        assert loan.due_date is None


@pytest.mark.asyncio
async def test_user_cannot_approve(
    session,
    client,
    token,
):
    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    resp_request = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    loan_db = resp_request.json()

    resp_approve = client.patch(
        f'{ENDPOINT_URL}/{loan_db["id"]}/approve',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp_approve.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_user_cannot_reject(session, client, token):
    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    resp_request = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    loan_db = resp_request.json()

    resp = client.patch(
        f'{ENDPOINT_URL}/{loan_db["id"]}/reject',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == HTTPStatus.FORBIDDEN


@pytest.mark.asyncio
async def test_user_cannot_list_all(session, client, token):
    resp = client.get(
        ENDPOINT_URL,
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert (
        resp.json()['detail']
        == 'Access forbidden. User role does not permit this action.'
    )


@pytest.mark.asyncio
async def test_list_loans_filter_by_status(session, client, token_admin, user):
    # Cria livro
    book = Book(
        isbn='111',
        title='Test Book',
        author='Author',
        publisher='Pub',
        edition=1,
        year=2024,
    )
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan1 = Loan(book_id=book.id, user_id=user.id, status=LoanStatus.BORROWED)
    session.add(loan1)

    loan2 = Loan(book_id=book.id, user_id=user.id, status=LoanStatus.REQUESTED)
    session.add(loan2)

    await session.commit()

    resp = client.get(
        f'{ENDPOINT_URL}?status=borrowed',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.OK
    items = resp.json()['loans']

    assert len(items) == 1
    assert items[0]['status'] == LoanStatus.BORROWED


@pytest.mark.asyncio
async def test_list_loans_invalid_status_returns_400(client, token_admin):
    resp = client.get(
        f'{ENDPOINT_URL}?status=INVALID_STATUS',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert 'Invalid status' in resp.json()['detail']


@pytest.mark.asyncio
async def test_list_loans_search_filters_results(
    session, client, token_admin, user
):
    book1 = Book(
        isbn='123-ABC',
        title='Python Avançado',
        author='João Silva',
        publisher='Editora X',
        edition=1,
        year=2022,
        quantity=1,
        available_quantity=0,
    )

    book2 = Book(
        isbn='999-XYZ',
        title='Rust Básico',
        author='Maria Souza',
        publisher='Editora Y',
        edition=1,
        year=2022,
        quantity=1,
        available_quantity=0,
    )

    session.add_all([book1, book2])
    await session.commit()
    await session.refresh(book1)
    await session.refresh(book2)

    loan1 = Loan(book_id=book1.id, user_id=user.id, status=LoanStatus.BORROWED)
    loan2 = Loan(book_id=book2.id, user_id=user.id, status=LoanStatus.BORROWED)
    session.add_all([loan1, loan2])
    await session.commit()

    resp = client.get(
        f'{ENDPOINT_URL}?search=Python',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.OK
    items = resp.json()['loans']

    assert len(items) == 1
    assert items[0]['book']['title'] == 'Python Avançado'


@pytest.mark.asyncio
async def test_list_loans_search_matches_user_name(
    session, client, token_admin, user
):
    book = Book(
        isbn='333',
        title='Qualquer',
        author='Outro',
        publisher='Editora Z',
        edition=1,
        year=2021,
        quantity=1,
        available_quantity=0,
    )
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan = Loan(book_id=book.id, user_id=user.id, status=LoanStatus.BORROWED)
    session.add(loan)
    await session.commit()

    search_piece = user.name.split()[0][:3]

    resp = client.get(
        f'{ENDPOINT_URL}?search={search_piece}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.OK
    items = resp.json()['loans']

    assert len(items) == 1
    assert items[0]['user']['id'] == user.id


@pytest.mark.asyncio
async def test_list_loans_invalid_sort_field_returns_422(client, token_admin):
    resp = client.get(
        f'{ENDPOINT_URL}?sort_by=invalid_field',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    detail = resp.json()['detail']
    assert detail[0]['msg'].startswith('String should match pattern')


@pytest.mark.asyncio
async def test_list_loans_sort_by_due_date(client, token_admin):
    resp = client.get(
        f'{ENDPOINT_URL}?sort_by=due_date&sort_order=asc',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert 'loans' in data


@pytest.mark.asyncio
async def test_return_loan_not_found(client, token):
    resp = client.patch(
        f'{ENDPOINT_URL}/9999/return',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert 'not found' in resp.json()['detail'].lower()


@pytest.mark.asyncio
async def test_return_loan_forbidden_for_other_user(
    session, client, user, token, other_user
):
    book = Book(
        isbn='222',
        title='Test',
        author='A',
        publisher='P',
        edition=1,
        year=2020,
    )
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan = Loan(
        book_id=book.id, user_id=other_user.id, status=LoanStatus.BORROWED
    )
    session.add(loan)
    await session.commit()
    await session.refresh(loan)

    resp = client.patch(
        f'{ENDPOINT_URL}/{loan.id}/return',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert resp.status_code == HTTPStatus.FORBIDDEN
    assert 'not allowed' in resp.json()['detail'].lower()


@pytest.mark.asyncio
async def test_return_loan_mark_as_returned_raises_400(
    session, client, user, token
):
    book = Book(
        isbn='333',
        title='Erro',
        author='X',
        publisher='Y',
        edition=1,
        year=2020,
        quantity=1,
        available_quantity=0,
    )
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan = Loan(book_id=book.id, user_id=user.id, status=LoanStatus.BORROWED)
    session.add(loan)
    await session.commit()
    await session.refresh(loan)

    with patch.object(
        Loan, 'mark_as_returned', side_effect=ValueError('invalid')
    ):
        resp = client.patch(
            f'{ENDPOINT_URL}/{loan.id}/return',
            headers={'Authorization': f'Bearer {token}'},
        )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert 'invalid' in resp.json()['detail']


@pytest.mark.asyncio
async def test_list_loans_pagination(session, client, token_admin, user):
    LIMIT = 2
    books = []
    for i in range(3):
        b = Book(
            isbn=f'pag{i}',
            title=f'Book {i}',
            author='A',
            publisher='P',
            edition=1,
            year=2020 + i,
            quantity=1,
            available_quantity=0,
        )
        books.append(b)
    session.add_all(books)
    await session.commit()
    for b in books:
        await session.refresh(b)

    loans = [Loan(book_id=books[i].id, user_id=user.id) for i in range(3)]
    session.add_all(loans)
    await session.commit()

    resp = client.get(
        f'{ENDPOINT_URL}?limit={LIMIT}&offset=0',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert resp.status_code == HTTPStatus.OK
    data = resp.json()
    assert data['meta']['size'] == LIMIT
    assert len(data['loans']) == LIMIT
    assert data['meta']['has_next'] is True

    resp2 = client.get(
        f'{ENDPOINT_URL}?limit=2&offset={LIMIT}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert resp2.status_code == HTTPStatus.OK
    data2 = resp2.json()
    assert len(data2['loans']) == 1
    assert data2['meta']['has_prev'] is True
