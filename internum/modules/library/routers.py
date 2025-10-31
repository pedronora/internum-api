import math
from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.core.permissions import CurrentUser, VerifyAdminCoord
from internum.modules.library.models import Book
from internum.modules.library.schemas import (
    BookCreate,
    BookCreated,
    BookQueryParams,
    BookSchema,
    BookUpdateSchema,
    PageMeta,
    PaginatedBooksList,
)

router = APIRouter(prefix='/library', tags=['Library'])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    '/books', status_code=HTTPStatus.CREATED, response_model=BookCreated
)
async def create_book(
    session: Session, book: BookCreate, current_user: VerifyAdminCoord
):
    stmt = select(Book).where(Book.isbn == book.isbn)
    existing = await session.scalar(stmt)

    if existing:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail='Book with this ISBN already exists.',
        )

    book_db = Book(
        isbn=book.isbn,
        title=book.title,
        author=book.author,
        publisher=book.publisher,
        edition=book.edition,
        year=book.year,
        quantity=1,
        available_quantity=1,
    )

    book_db.created_by_id = current_user.id

    session.add(book_db)
    await session.commit()
    await session.refresh(book_db)

    return book_db


@router.get(
    '/books', status_code=HTTPStatus.OK, response_model=PaginatedBooksList
)
async def list_books(
    session: Session,
    params: Annotated[BookQueryParams, Depends()],
    current_user: CurrentUser,
):
    limit = max(1, params.limit)
    offset = max(0, params.offset)
    search = params.search

    filters = [Book.deleted_at.is_(None)]

    if search:
        search_pattern = f'%{search}%'

        search_filters = or_(
            Book.isbn.ilike(search_pattern),
            Book.title.ilike(search_pattern),
            Book.author.ilike(search_pattern),
        )

        filters.append(search_filters)

    total: int = (
        await session.scalar(
            select(func.count()).select_from(Book).where(*filters)
        )
    ) or 0

    query_stmt = (
        select(Book)
        .options(
            selectinload(Book.loans),
        )
        .order_by(Book.title)
        .offset(offset)
        .limit(limit)
        .where(*filters)
    )

    query = await session.scalars(query_stmt)
    books = query.all()

    total_pages = math.ceil(total / limit) if limit > 0 else 1
    page = (offset // limit) + 1 if limit > 0 else 1
    has_next = (offset + limit) < total
    has_prev = offset > 0

    meta = PageMeta(
        total=total,
        page=page,
        size=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
        offset=offset,
    )

    return {'meta': meta, 'books': books}


@router.get(
    '/books/{book_id}', status_code=HTTPStatus.OK, response_model=BookSchema
)
async def get_book_by_id(
    session: Session, book_id: int, current_user: CurrentUser
):
    book_db = await session.scalar(
        select(Book)
        .options(
            selectinload(Book.loans),
        )
        .where(Book.id == book_id, Book.deleted_at.is_(None))
    )

    if not book_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Book with id ({book_id}) not found.',
        )

    return book_db


@router.put(
    '/books/{book_id}', status_code=HTTPStatus.OK, response_model=BookSchema
)
async def update_book(
    session: Session,
    book_id: int,
    book_update: BookUpdateSchema,
    current_user: CurrentUser,
):
    book_db = await session.scalar(
        select(Book)
        .options(
            selectinload(Book.loans),
        )
        .where(Book.id == book_id, Book.deleted_at.is_(None))
    )

    if not book_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Book with id ({book_id}) not found.',
        )

    for field, value in book_update.dict(exclude_unset=True).items():
        setattr(book_db, field, value)

    book_db.updated_at = datetime.utcnow()

    session.add(book_db)
    await session.commit()
    await session.refresh(book_db)

    return book_db


@router.delete('/books/{book_id}', status_code=HTTPStatus.NO_CONTENT)
async def soft_delete_book(
    session: Session, book_id: int, current_user: CurrentUser
):
    book_db = await session.scalar(
        select(Book).where(Book.id == book_id, Book.deleted_at.is_(None))
    )

    if not book_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Book with id ({book_id}) not found.',
        )

    book_db.soft_delete(current_user.id)

    session.add(book_db)
    await session.commit()
