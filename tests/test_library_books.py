from http import HTTPStatus

import factory
import pytest
from sqlalchemy import select

from internum.modules.library.models import Book

ENDPOINT_URL = '/api/v1/library/books'


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
async def test_create_book_success(client, session, user_admin, token_admin):
    payload = {
        'isbn': '1234567890',
        'title': 'Clean Architecture',
        'author': 'Robert C. Martin',
        'publisher': 'Pearson',
        'edition': 1,
        'year': 2017,
    }

    response = client.post(
        ENDPOINT_URL,
        json=payload,
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data['isbn'] == payload['isbn']
    assert data['title'] == payload['title']

    result = await session.scalar(
        select(Book).where(Book.isbn == payload['isbn'])
    )
    assert result is not None
    assert result.created_by_id == user_admin.id


@pytest.mark.asyncio
async def test_create_book_conflict(client, session, token_admin):
    client.post(
        ENDPOINT_URL,
        json={
            'isbn': '123456789',
            'title': 'Duplicated ISBN',
            'author': 'Someone',
            'publisher': 'Pub',
            'edition': 2,
            'year': 2021,
        },
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    response = client.post(
        ENDPOINT_URL,
        json={
            'isbn': '123456789',
            'title': 'Duplicated ISBN',
            'author': 'Someone',
            'publisher': 'Pub',
            'edition': 2,
            'year': 2021,
        },
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert 'already exists' in response.json()['detail']


@pytest.mark.asyncio
async def test_create_book_unauthorized(client):
    payload = {
        'isbn': '1234567890',
        'title': 'Test Book',
        'author': 'Test Author',
        'publisher': 'Test Publisher',
        'edition': 1,
        'year': 2023,
    }

    response = client.post(ENDPOINT_URL, json=payload)

    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_list_books_default(
    client,
    session,
    user_admin,
    token,
):
    expected_books = 5
    books_list = BookFactory.create_batch(expected_books)
    for book in books_list:
        book.created_by_id = user_admin.id

    session.add_all(books_list)
    await session.commit()

    response = client.get(
        ENDPOINT_URL, headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert 'meta' in data
    assert len(data['books']) == expected_books


@pytest.mark.asyncio
async def test_list_books_with_search(client, session, user_admin, token):
    book_a = BookFactory(title='Python Tricks')
    book_a.created_by_id = user_admin.id
    book_b = BookFactory(title='JavaScript Guide')
    book_b.created_by_id = user_admin.id

    session.add_all([book_a, book_b])
    await session.commit()

    response = client.get(
        ENDPOINT_URL + '?search=Python',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data['books']) == 1
    assert data['books'][0]['title'] == 'Python Tricks'


@pytest.mark.asyncio
async def test_get_book_success(client, session, user_admin, token):
    book = BookFactory()
    book.created_by_id = user_admin.id
    session.add(book)
    await session.commit()
    await session.refresh(book)

    response = client.get(
        ENDPOINT_URL + f'/{book.id}',
        headers={'Authorization': f'Bearer {token}'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['title'] == book.title


def test_get_book_not_found(client, token):
    response = client.get(
        ENDPOINT_URL + '/9999', headers={'Authorization': f'Bearer {token}'}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_update_book_success(session, client, user_admin, token_admin):
    book = BookFactory(title='Old Title')
    book.created_by_id = user_admin.id
    session.add(book)
    await session.commit()
    await session.refresh(book)

    response = client.put(
        ENDPOINT_URL + f'/{book.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
        json={'title': 'New Title'},
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data['title'] == 'New Title'


def test_update_book_not_found(client, token_admin):
    response = client.put(
        ENDPOINT_URL + '/9999',
        json={'title': 'Whatever'},
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_soft_delete_success(client, session, token_admin, user_admin):
    book = BookFactory()
    book.created_by_id = user_admin.id
    session.add(book)
    await session.commit()
    await session.refresh(book)

    response = client.delete(
        ENDPOINT_URL + f'/{book.id}',
        headers={'Authorization': f'Bearer {token_admin}'},
    )

    assert response.status_code == HTTPStatus.NO_CONTENT

    refreshed = await session.scalar(select(Book).where(Book.id == book.id))
    assert refreshed.deleted_at is not None
    assert refreshed.deleted_by_id == user_admin.id


def test_soft_delete_not_found(client, token_admin):
    response = client.delete(
        ENDPOINT_URL + '/9999',
        headers={'Authorization': f'Bearer {token_admin}'},
    )
    assert response.status_code == HTTPStatus.NOT_FOUND
