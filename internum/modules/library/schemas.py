from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field

from internum.modules.library.enums import LoanStatus


class UserPublic(BaseModel):
    id: int
    name: str

    model_config = dict(from_attributes=True)


class LoanSchema(BaseModel):
    id: int
    book_id: int
    user: UserPublic
    status: LoanStatus = LoanStatus.REQUESTED
    approved_by: Optional[UserPublic]
    borrowed_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    returned_at: Optional[datetime] = None

    model_config = dict(from_attributes=True)


class LoanQueryParams(BaseModel):
    limit: int = Query(default=10, ge=1, description='Itens por página')
    offset: int = Query(default=0, ge=0, description='Itens a pular')
    status: Optional[str] = Query(
        default=None, description='Filtrar por status'
    )
    search: Optional[str] = Query(
        default=None,
        description='Buscar por livro (título, autor, ISBN) ou usuário',
        min_length=1,
    )
    sort_by: str = Query(
        default='created_at',
        pattern='^(created_at|due_date)$',
        description='Campo de ordenação',
    )
    sort_order: str = Query(
        default='desc',
        pattern='^(asc|desc)$',
        description='Ordem de ordenação',
    )


class PageMeta(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    offset: int


class PaginatedLoansList(BaseModel):
    meta: PageMeta
    loans: list['LoanSchema']


class BookBaseSchema(BaseModel):
    id: int
    isbn: str
    title: str
    author: str
    publisher: str
    edition: int
    year: int
    quantity: int
    available_quantity: int


class BookDetailSchema(BookBaseSchema):
    loans: list[LoanSchema] = Field(default_factory=list)


class BookCreateSchema(BaseModel):
    isbn: str
    title: str
    author: str
    publisher: str
    edition: int
    year: int


class BookUpdateSchema(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[int] = None
    year: Optional[int] = None
    quantity: Optional[int] = None


class BookQueryParams(BaseModel):
    limit: int = Query(
        default=10, ge=1, description='Número de itens por página'
    )
    offset: int = Query(default=0, ge=0, description='Número de itens a pular')

    search: Optional[str] = Query(
        default=None,
        min_length=1,
        description='Termo de busca para os campos: ISBN, título e autor',
    )


class PaginatedBooksList(BaseModel):
    meta: PageMeta
    books: list[BookBaseSchema]
