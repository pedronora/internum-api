from http import HTTPStatus

import factory
import pytest
from sqlalchemy import select

from internum.modules.library.models import Book, Loan

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
async def test_request_loan_success(session, client, user, token):
    book = BookFactory(quantity=2, available_quantity=2)
    book.created_by_id = user.id
    session.add(book)
    await session.commit()
    await session.refresh(book)

    response = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['book_id'] == book.id
    assert data['status'] == 'requested'


@pytest.mark.asyncio
async def test_request_loan_unavailable_book(session, client, user, token):
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
    assert 'not available' in response.json().get('detail', '').lower()


@pytest.mark.asyncio
async def test_approve_loan_success(
    session, client, token, user_admin, token_admin
):
    book = BookFactory(quantity=1, available_quantity=1)
    session.add(book)
    await session.commit()
    await session.refresh(book)

    loan = Loan(book_id=book.id, user_id=user_admin.id)
    session.add(loan)
    await session.commit()
    await session.refresh(loan)

    client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    response = client.patch(
        f'{ENDPOINT_URL}/{loan.id}/approve',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'borrowed'
    assert data['approved_by']['id'] == user_admin.id


@pytest.mark.asyncio
async def test_reject_loan_success(session, client, user, token, token_admin):
    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    response = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    loan = response.json()

    response = client.patch(
        f'{ENDPOINT_URL}/{loan["id"]}/reject',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'rejected'


@pytest.mark.asyncio
async def test_return_loan_success(session, client, token, token_admin):
    book = BookFactory()
    session.add(book)
    await session.commit()
    await session.refresh(book)

    response = client.post(
        f'{ENDPOINT_URL}/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    loan = response.json()

    response = client.patch(
        f'{ENDPOINT_URL}/{loan["id"]}/approve',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    response = client.patch(
        f'{ENDPOINT_URL}/{loan["id"]}/return',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['status'] == 'returned'

    updated_book = await session.scalar(select(Book).where(Book.id == book.id))
    assert updated_book.available_quantity == 1


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
