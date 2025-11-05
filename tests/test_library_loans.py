from http import HTTPStatus

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
async def test_loan_flow_success(session, client, token, token_admin, user):
    # Cria um livro disponível
    book = BookFactory(quantity=1, available_quantity=1)
    session.add(book)
    await session.commit()
    await session.refresh(book)

    # 1️⃣ Usuário solicita empréstimo
    resp = client.post(
        ENDPOINT_URL + f'/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == HTTPStatus.CREATED
    loan = resp.json()
    assert loan['status'] == LoanStatus.REQUESTED

    loan_id = loan['id']

    # 2️⃣ Admin aprova empréstimo
    resp = client.patch(
        ENDPOINT_URL + f'/{loan_id}/approve',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.BORROWED

    # 3️⃣ Usuário devolve o livro
    resp = client.patch(
        ENDPOINT_URL + f'/{loan_id}/return',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.RETURNED


@pytest.mark.asyncio
async def test_loan_flow_cancel_by_user(session, client, token, user):
    book = BookFactory(quantity=1, available_quantity=1)
    session.add(book)
    await session.commit()
    await session.refresh(book)

    resp = client.post(
        ENDPOINT_URL + f'/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )

    loan_id = resp.json()['id']

    resp = client.patch(
        ENDPOINT_URL + f'/{loan_id}/cancel',
        headers={'Authorization': f'Bearer {token}'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.CANCELED


@pytest.mark.asyncio
async def test_loan_flow_reject_by_admin(
    session, client, token, token_admin, user
):
    book = BookFactory(quantity=1, available_quantity=1)
    session.add(book)
    await session.commit()
    await session.refresh(book)

    resp = client.post(
        ENDPOINT_URL + f'/{book.id}/request',
        headers={'Authorization': f'Bearer {token}'},
    )
    loan_id = resp.json()['id']

    resp = client.patch(
        ENDPOINT_URL + f'/{loan_id}/reject',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()['status'] == LoanStatus.REJECTED


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
