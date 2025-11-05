import math
from datetime import datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.core.permissions import CurrentUser, VerifyAdminCoord
from internum.modules.library.enums import LoanStatus
from internum.modules.library.models import Book, Loan
from internum.modules.library.schemas import (
    BookBaseSchema,
    BookCreateSchema,
    BookDetailSchema,
    BookQueryParams,
    BookUpdateSchema,
    LoanBriefSchema,
    LoanQueryParams,
    LoanSchema,
    PageMeta,
    PaginatedBooksList,
    PaginatedLoansList,
)
from internum.modules.users.models import User

router = APIRouter(prefix='/library', tags=['Library'])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    '/books', status_code=HTTPStatus.CREATED, response_model=BookBaseSchema
)
async def create_book(
    session: Session, book: BookCreateSchema, current_user: VerifyAdminCoord
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
    '/books/{book_id}',
    status_code=HTTPStatus.OK,
    response_model=BookDetailSchema,
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
    '/books/{book_id}',
    status_code=HTTPStatus.OK,
    response_model=BookBaseSchema,
)
async def update_book(
    session: Session,
    book_id: int,
    book_update: BookUpdateSchema,
    current_user: VerifyAdminCoord,
):
    book_db = await session.scalar(
        select(Book).where(Book.id == book_id, Book.deleted_at.is_(None))
    )

    if not book_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Book with id ({book_id}) not found.',
        )

    update_data = book_update.dict(exclude_unset=True)

    update_data['updated_at'] = datetime.utcnow()

    if book_update.quantity is not None:
        diff = book_update.quantity - book_db.quantity
        book_db.quantity = book_update.quantity
        book_db.available_quantity += diff

    book_db.available_quantity = max(book_db.available_quantity, 0)

    for field, value in update_data.items():
        if field == 'quantity':
            continue
        if hasattr(book_db, field):
            setattr(book_db, field, value)

    book_db.mark_updated(current_user.id)

    session.add(book_db)
    await session.commit()
    await session.refresh(book_db)

    return book_db


@router.delete('/books/{book_id}', status_code=HTTPStatus.NO_CONTENT)
async def soft_delete_book(
    session: Session, book_id: int, current_user: VerifyAdminCoord
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


@router.post(
    '/loans/{book_id}/request',
    status_code=HTTPStatus.CREATED,
    response_model=LoanBriefSchema,
)
async def request_loan(
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

    new_loan = Loan(book_id=book_id, user_id=current_user.id)

    try:
        book_db.lend()
    except ValueError as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(e),
        )

    session.add_all([new_loan, book_db])
    await session.commit()
    await session.refresh(new_loan)

    return new_loan


@router.patch(
    '/loans/{loan_id}/cancel',
    status_code=HTTPStatus.OK,
    response_model=LoanBriefSchema,
)
async def cancel_loan(
    loan_id: int, session: Session, current_user: CurrentUser
):
    loan_db = await session.scalar(
        select(Loan).where(Loan.id == loan_id, Loan.deleted_at.is_(None))
    )

    if not loan_db:
        raise HTTPException(status_code=404, detail='Loan not found.')

    if loan_db.status != LoanStatus.REQUESTED:
        raise HTTPException(
            status_code=400, detail='Only pending requests can be canceled.'
        )

    loan_db.status = LoanStatus.CANCELED
    loan_db.updated_by_id = current_user.id
    loan_db.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(loan_db)

    return loan_db


@router.patch(
    '/loans/{loan_id}/approve',
    status_code=HTTPStatus.OK,
    response_model=LoanBriefSchema,
)
async def approve_and_start_loan(
    session: Session,
    loan_id: int,
    current_user: VerifyAdminCoord,
):
    loan_db = await session.scalar(
        select(Loan).where(Loan.id == loan_id, Loan.deleted_at.is_(None))
    )

    if not loan_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Loan with id ({loan_id}) not found.',
        )

    try:
        loan_db.approve_and_start(current_user)
        loan_db.mark_updated(current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

    session.add(loan_db)
    await session.commit()
    await session.refresh(loan_db)

    return loan_db


@router.patch(
    '/loans/{loan_id}/return',
    status_code=HTTPStatus.OK,
    response_model=LoanBriefSchema,
)
async def return_loan(
    session: Session,
    loan_id: int,
    current_user: CurrentUser,
):
    loan_db = await session.scalar(
        select(Loan).where(Loan.id == loan_id, Loan.deleted_at.is_(None))
    )

    if not loan_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Loan with id ({loan_id}) not found.',
        )

    if loan_db.user_id != current_user.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='You are not allowed to return this loan.',
        )

    try:
        loan_db.mark_as_returned()
        loan_db.mark_updated(current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

    session.add(loan_db)
    await session.commit()
    await session.refresh(loan_db)

    return loan_db


@router.patch(
    '/loans/{loan_id}/reject',
    status_code=HTTPStatus.OK,
    response_model=LoanBriefSchema,
)
async def reject_loan(
    session: Session, loan_id: int, current_user: VerifyAdminCoord
):
    loan_db = await session.scalar(
        select(Loan).where(Loan.id == loan_id, Loan.deleted_at.is_(None))
    )

    if not loan_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Loan with id ({loan_id}) not found.',
        )

    try:
        loan_db.reject(current_user)
        loan_db.mark_updated(current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))

    session.add(loan_db)
    await session.commit()
    await session.refresh(loan_db)

    return loan_db


@router.get(
    '/loans',
    response_model=PaginatedLoansList,
    status_code=HTTPStatus.OK,
)
async def list_loans(
    session: Session,
    current_user: VerifyAdminCoord,
    params: Annotated[LoanQueryParams, Depends()],
):
    stmt = select(Loan).options(
        selectinload(Loan.book),
        selectinload(Loan.user),
        selectinload(Loan.approved_by),
    )

    filters = []

    if params.status:
        try:
            status_enum = LoanStatus(params.status)
            filters.append(Loan.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid status '{params.status}'.",
            )

    if params.search:
        search_pattern = f'%{params.search}%'
        filters.append(
            or_(
                Book.title.ilike(search_pattern),
                Book.author.ilike(search_pattern),
                Book.isbn.ilike(search_pattern),
                Loan.user.has(User.name.ilike(search_pattern)),
            )
        )

    if filters:
        stmt = stmt.where(*filters)

    total = (
        await session.scalar(select(func.count()).select_from(stmt.subquery()))
    ) or 0

    sort_column = getattr(Loan, params.sort_by)
    sort_func = asc if params.sort_order == 'asc' else desc
    stmt = stmt.order_by(sort_func(sort_column))
    stmt = stmt.offset(params.offset).limit(params.limit)

    loans = (await session.scalars(stmt)).all()

    total_pages = (total + params.limit - 1) // params.limit
    current_page = (params.offset // params.limit) + 1

    meta = PageMeta(
        total=total,
        page=current_page,
        size=params.limit,
        total_pages=total_pages,
        has_next=params.offset + params.limit < total,
        has_prev=params.offset > 0,
        offset=params.offset,
    )

    return PaginatedLoansList(meta=meta, loans=loans)


@router.get(
    '/loans/my',
    response_model=PaginatedLoansList,
    status_code=HTTPStatus.OK,
)
async def list_my_loans(
    session: Session,
    current_user: CurrentUser,
    params: Annotated[LoanQueryParams, Depends()],
):
    stmt = (
        select(Loan)
        .where(Loan.user_id == current_user.id)
        .options(
            selectinload(Loan.book),
            selectinload(Loan.user),
            selectinload(Loan.approved_by),
        )
    )

    if params.status:
        try:
            status_enum = LoanStatus(params.status)
            stmt = stmt.where(Loan.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid status '{params.status}'",
            )

    total = (
        await session.scalar(select(func.count()).select_from(stmt.subquery()))
    ) or 0

    sort_column = getattr(Loan, params.sort_by, Loan.created_at)
    sort_func = asc if params.sort_order == 'asc' else desc
    stmt = stmt.order_by(sort_func(sort_column))

    stmt = stmt.offset(params.offset).limit(params.limit)
    loans = (await session.scalars(stmt)).all()

    total_pages = (total + params.limit - 1) // params.limit
    current_page = (params.offset // params.limit) + 1

    meta = PageMeta(
        total=total,
        page=current_page,
        size=params.limit,
        total_pages=total_pages,
        has_next=params.offset + params.limit < total,
        has_prev=params.offset > 0,
        offset=params.offset,
    )

    loan_schemas = [LoanSchema.from_orm(loan) for loan in loans]
    return PaginatedLoansList(meta=meta, loans=loan_schemas)
