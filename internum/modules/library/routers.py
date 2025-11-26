from datetime import datetime
from http import HTTPStatus
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from internum.core.database import get_session
from internum.core.email import EmailService
from internum.core.permissions import CurrentUser
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
    PageMeta,
    PaginatedBooksList,
    PaginatedLoansList,
)
from internum.modules.users.models import User

router = APIRouter(prefix='/library', tags=['Library'])
Session = Annotated[AsyncSession, Depends(get_session)]

email_service = EmailService()


ALLOWED_SORT_FIELDS = {
    'id': Loan.id,
    'status': Loan.status,
    'created_at': Loan.created_at,
    'updated_at': Loan.updated_at,
    'due_date': Loan.due_date,
}


@router.post(
    '/books', status_code=HTTPStatus.CREATED, response_model=BookBaseSchema
)
async def create_book(
    session: Session, book: BookCreateSchema, current_user: CurrentUser
):
    if current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='You are not allowed to create a loan.',
        )

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
    '/books',
    status_code=HTTPStatus.OK,
    response_model=PaginatedBooksList,
)
async def list_books(
    session: Session,
    params: Annotated[BookQueryParams, Depends()],
    current_user: CurrentUser,
):
    limit = max(1, params.limit)
    offset = max(0, params.offset)

    filters = [Book.deleted_at.is_(None)]

    if params.search:
        search_pattern = f'%{params.search}%'
        filters.append(
            or_(
                Book.title.ilike(search_pattern),
                Book.author.ilike(search_pattern),
                Book.isbn.ilike(search_pattern),
            )
        )

    count_stmt = select(func.count()).select_from(Book).where(*filters)
    total = (await session.scalar(count_stmt)) or 0

    stmt = (
        select(Book)
        .options(selectinload(Book.loans))
        .where(*filters)
        .order_by(Book.title.asc())
        .offset(offset)
        .limit(limit)
    )

    books = (await session.scalars(stmt)).unique().all()

    total_pages = (total + limit - 1) // limit
    current_page = (offset // limit) + 1

    meta = PageMeta(
        total=total,
        page=current_page,
        size=limit,
        total_pages=total_pages,
        has_next=offset + limit < total,
        has_prev=offset > 0,
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
    current_user: CurrentUser,
):
    if current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='You are not allowed to update this loan.',
        )

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
    session: Session, book_id: int, current_user: CurrentUser
):
    if current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='You are not allowed to delete this loan.',
        )

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
    session: Session,
    book_id: int,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    book_db = await session.scalar(
        select(Book).where(Book.id == book_id, Book.deleted_at.is_(None))
    )

    if not book_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Book with id ({book_id}) not found.',
        )

    new_loan = Loan(book_id=book_id)
    new_loan.created_by_id = current_user.id

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

    requested_str = new_loan.created_at.astimezone(
        ZoneInfo('America/Sao_Paulo')
    ).strftime('%d/%m/%Y %H:%M:%S')

    html_content = f"""
    <html>
      <body
        style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4CAF50;">
            Confirmação de Solicitação de Empréstimo
        </h2>
        <p>Olá, {current_user.name}:</p>
        <p>Seu pedido de empréstimo foi registrado com sucesso e será avaliado
         pela coordenação.</p>
        <h3>Detalhes do Livro:</h3>
        <ul>
          <li><strong>Título:</strong> {book_db.title}</li>
          <li><strong>Autor:</strong> {book_db.author}</li>
        </ul>
        <p><strong>Data/Hora da Solicitação:</strong> {requested_str}</p>
        <hr>
        <p style="font-size: 0.9em; color: #888;">
          Esta é uma mensagem automática do sistema I
          nternum - 1º SRI de Cascavel/PR.
        </p>
      </body>
    </html>
    """

    background_tasks.add_task(
        email_service.send_email,
        email_to=[current_user.email],
        subject='[Internum] Confirmação de Solicitação de Empréstimo',
        html=html_content,
        category='Loan Request',
    )

    return new_loan


@router.patch(
    '/loans/{loan_id}/cancel',
    status_code=HTTPStatus.OK,
    response_model=LoanBriefSchema,
)
async def cancel_loan(
    loan_id: int,
    session: Session,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    loan_db = await session.scalar(
        select(Loan)
        .options(selectinload(Loan.book), selectinload(Loan.created_by))
        .where(Loan.id == loan_id, Loan.deleted_at.is_(None))
    )

    if not loan_db:
        raise HTTPException(status_code=404, detail='Loan not found.')

    if loan_db.status != LoanStatus.REQUESTED:
        raise HTTPException(
            status_code=400, detail='Only pending requests can be canceled.'
        )

    if loan_db.created_by_id != current_user.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='You are not allowed to cancel this loan.',
        )

    loan_db.mark_as_canceled()
    loan_db.updated_by_id = current_user.id
    loan_db.updated_at = datetime.utcnow()

    await session.commit()
    await session.refresh(loan_db)

    canceled_str = loan_db.updated_at.astimezone(
        ZoneInfo('America/Sao_Paulo')
    ).strftime('%d/%m/%Y %H:%M:%S')

    html_content = f"""
    <html>
      <body
        style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4CAF50;">
            Confirmação de Cancelamento de Empréstimo
        </h2>
        <p>Olá, {current_user.name}:</p>
        <p>Você cancelou seu pedido de emréstimo.</p>
        <h3>Detalhes do Empréstimo:</h3>
        <ul>
          <li><strong>Título:</strong> {loan_db.book.title}</li>
          <li><strong>Autor:</strong> {loan_db.book.author}</li>
        </ul>
        <p><strong>Data/Hora do Cancelamento:</strong> {canceled_str}</p>
        <hr>
        <p style="font-size: 0.9em; color: #888;">
          Esta é uma mensagem automática do sistema I
          nternum - 1º SRI de Cascavel/PR.
        </p>
      </body>
    </html>
    """

    background_tasks.add_task(
        email_service.send_email,
        email_to=[current_user.email],
        subject='[Internum] Confirmação de Cancelamento de Empréstimo',
        html=html_content,
        category='Loan Cancel',
    )

    return loan_db


@router.patch(
    '/loans/{loan_id}/approve',
    status_code=HTTPStatus.OK,
    response_model=LoanBriefSchema,
)
async def approve_and_start_loan(
    session: Session,
    loan_id: int,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    if current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='You are not allowed to approve this loan.',
        )

    loan_db = await session.scalar(
        select(Loan)
        .where(Loan.id == loan_id, Loan.deleted_at.is_(None))
        .options(selectinload(Loan.book), selectinload(Loan.created_by))
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

    requested_str = loan_db.borrowed_at.astimezone(
        ZoneInfo('America/Sao_Paulo')
    ).strftime('%d/%m/%Y %H:%M:%S')
    due_date_str = loan_db.due_date.astimezone(
        ZoneInfo('America/Sao_Paulo')
    ).strftime('%d/%m/%Y')

    html_content = f"""
    <html>
      <body
        style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4CAF50;">
            Confirmação de Aprovação de Empréstimo
        </h2>
        <p>Olá, {current_user.name}:</p>
        <p>Seu pedido de empréstimo foi aprovado pela coordenação.</p>
        <h3>Detalhes do Empréstimo:</h3>
        <ul>
          <li><strong>Título:</strong> {loan_db.book.title}</li>
          <li><strong>Autor:</strong> {loan_db.book.author}</li>
          <li><strong>Devolver até:</strong> {due_date_str}
        </ul>
        <p><strong>Data/Hora da Solicitação:</strong> {requested_str}</p>
        <hr>
        <p style="font-size: 0.9em; color: #888;">
          Esta é uma mensagem automática do sistema I
          nternum - 1º SRI de Cascavel/PR.
        </p>
      </body>
    </html>
    """

    background_tasks.add_task(
        email_service.send_email,
        email_to=[loan_db.created_by.email],
        subject='[Internum] Confirmação de Aprovação de Empréstimo',
        html=html_content,
        category='Loan Approve',
    )

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
    background_tasks: BackgroundTasks,
):
    loan_db = await session.scalar(
        select(Loan)
        .options(selectinload(Loan.book), selectinload(Loan.created_by))
        .where(Loan.id == loan_id, Loan.deleted_at.is_(None))
    )

    if not loan_db:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f'Loan with id ({loan_id}) not found.',
        )

    if loan_db.created_by_id != current_user.id and current_user.role not in {
        'admin',
        'coord',
    }:
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

    returned_str = loan_db.returned_at.astimezone(
        ZoneInfo('America/Sao_Paulo')
    ).strftime('%d/%m/%Y %H:%M:%S')

    html_content = f"""
    <html>
      <body
        style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4CAF50;">
            Confirmação de Devolução de Empréstimo
        </h2>
        <p>Olá, {current_user.name}:</p>
        <p>Seu empréstimo foi devolvido com sucesso.</p>
        <h3>Detalhes do Empréstimo:</h3>
        <ul>
          <li><strong>Título:</strong> {loan_db.book.title}</li>
          <li><strong>Autor:</strong> {loan_db.book.author}</li>
        </ul>
        <p><strong>Data/Hora da Devolução:</strong> {returned_str}</p>
        <hr>
        <p style="font-size: 0.9em; color: #888;">
          Esta é uma mensagem automática do sistema I
          nternum - 1º SRI de Cascavel/PR.
        </p>
      </body>
    </html>
    """

    background_tasks.add_task(
        email_service.send_email,
        email_to=[current_user.email],
        subject='[Internum] Confirmação de Devolução de Empréstimo',
        html=html_content,
        category='Loan Return',
    )

    return loan_db


@router.patch(
    '/loans/{loan_id}/reject',
    status_code=HTTPStatus.OK,
    response_model=LoanBriefSchema,
)
async def reject_loan(
    session: Session,
    loan_id: int,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
):
    if current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='You are not allowed to reject this loan.',
        )

    loan_db = await session.scalar(
        select(Loan)
        .options(selectinload(Loan.book), selectinload(Loan.created_by))
        .where(Loan.id == loan_id, Loan.deleted_at.is_(None))
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

    reject_str = loan_db.updated_at.astimezone(
        ZoneInfo('America/Sao_Paulo')
    ).strftime('%d/%m/%Y %H:%M:%S')

    html_content = f"""
    <html>
      <body
        style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2 style="color: #4CAF50;">
            Informação de Rejeição de Empréstimo
        </h2>
        <p>Olá, {current_user.name}:</p>
        <p>
        Seu empréstimo foi rejeitado pela coordenação. Para maiores detalhes, 
        procure seu coordendador
        </p>
        <h3>Detalhes do Empréstimo:</h3>
        <ul>
          <li><strong>Título:</strong> {loan_db.book.title}</li>
          <li><strong>Autor:</strong> {loan_db.book.author}</li>
        </ul>
        <p><strong>Data/Hora da Rejeição:</strong> {reject_str}</p>
        <hr>
        <p style="font-size: 0.9em; color: #888;">
          Esta é uma mensagem automática do sistema I
          nternum - 1º SRI de Cascavel/PR.
        </p>
      </body>
    </html>
    """  # noqa: W291

    background_tasks.add_task(
        email_service.send_email,
        email_to=[current_user.email],
        subject='[Internum] Informação de Rejeição de Empréstimo',
        html=html_content,
        category='Loan Reject',
    )

    return loan_db


@router.get(
    '/loans',
    response_model=PaginatedLoansList,
    status_code=HTTPStatus.OK,
)
async def list_loans(
    session: Session,
    current_user: CurrentUser,
    params: Annotated[LoanQueryParams, Depends()],
):
    if current_user.id and current_user.role not in {
        'admin',
        'coord',
    }:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail='Access forbidden. User role does not permit this action.',
        )

    stmt = select(Loan).options(
        selectinload(Loan.book),
        selectinload(Loan.created_by),
        selectinload(Loan.approved_by),
    )

    filters = []
    joins = []

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
        joins.append((Loan.book, Book))
        joins.append((Loan.created_by, User))

        filters.append(
            or_(
                Book.title.ilike(search_pattern),
                Book.author.ilike(search_pattern),
                Book.isbn.ilike(search_pattern),
                User.name.ilike(search_pattern),
            )
        )

    for relationship, model in joins:
        stmt = stmt.join(relationship)

    if filters:
        stmt = stmt.where(*filters)

    stmt = stmt.distinct()
    count_stmt = select(func.count(func.distinct(Loan.id))).select_from(Loan)

    for relationship, model in joins:
        count_stmt = count_stmt.join(relationship)
    if filters:
        count_stmt = count_stmt.where(*filters)

    total = (await session.scalar(count_stmt)) or 0

    sort_field = params.sort_by
    sort_column = ALLOWED_SORT_FIELDS[sort_field]
    sort_func = asc if params.sort_order == 'asc' else desc
    stmt = stmt.order_by(sort_func(sort_column))

    stmt = stmt.offset(params.offset).limit(params.limit)
    loans = (await session.scalars(stmt)).unique().all()

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
        .where(Loan.created_by_id == current_user.id)
        .options(
            selectinload(Loan.book),
            selectinload(Loan.created_by),
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

    count_stmt = (
        select(func.count())
        .select_from(Loan)
        .where(Loan.created_by_id == current_user.id)
    )
    if params.status:
        count_stmt = count_stmt.where(Loan.status == status_enum)
    total = (await session.scalar(count_stmt)) or 0

    sort_field = params.sort_by
    sort_column = ALLOWED_SORT_FIELDS[sort_field]
    sort_func = asc if params.sort_order == 'asc' else desc
    stmt = stmt.order_by(sort_func(sort_column))

    stmt = stmt.offset(params.offset).limit(params.limit)
    loans = (await session.scalars(stmt)).unique().all()

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
