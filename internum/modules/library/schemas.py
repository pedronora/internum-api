from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field, field_validator

from internum.modules.library.enums import LoanStatus


class UserBriefSchema(BaseModel):
    id: int
    name: str
    email: str

    model_config = dict(from_attributes=True)


class BookBriefSchema(BaseModel):
    id: int
    title: str
    author: str

    model_config = dict(from_attributes=True)


class LoanSchema(BaseModel):
    id: int
    book: BookBriefSchema
    user: UserBriefSchema = Field(
        ..., validation_alias='created_by', serialization_alias='user'
    )
    status: LoanStatus = LoanStatus.REQUESTED
    created_at: Optional[datetime] = None
    approved_by: Optional[UserBriefSchema]
    borrowed_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    returned_at: Optional[datetime] = None

    model_config = dict(from_attributes=True)


class LoanBriefSchema(BaseModel):
    id: int
    book_id: int
    user_id: int = Field(
        ..., validation_alias='created_by_id', serialization_alias='user_id'
    )
    status: LoanStatus

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

    @field_validator('title', 'author', 'publisher', mode='before')
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v  # pragma: no cover


class BookUpdateSchema(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[int] = None
    year: Optional[int] = None
    quantity: Optional[int] = None

    @field_validator('title', 'author', 'publisher', mode='before')
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v  # pragma: no cover


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
