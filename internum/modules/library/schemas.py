from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict

from internum.core.schemas import AuditSchema
from internum.modules.library.enums import LoanStatus


class UserPublic(BaseModel):
    id: int
    name: str


class LoanSchema(BaseModel):
    id: int
    book_id: int
    user_id: int
    status: LoanStatus = LoanStatus.REQUESTED
    approved_by_id: Optional[int] = None
    borrowed_at: Optional[datetime] = None
    due_date: Optional[datetime] = None
    returned_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BookCreated(AuditSchema):
    id: int
    isbn: str
    title: str
    author: str
    publisher: str
    edition: int
    year: int
    quantity: int
    available_quantity: int

    model_config = ConfigDict(from_attributes=True)


class BookSchema(AuditSchema):
    id: int
    isbn: str
    title: str
    author: str
    publisher: str
    edition: int
    year: int
    quantity: int
    available_quantity: int
    loans: list[LoanSchema] = []

    model_config = ConfigDict(from_attributes=True)


class BookCreate(BaseModel):
    isbn: str
    title: str
    author: str
    publisher: str
    edition: int
    year: int


class BookUpdateSchema(BaseModel):
    isbn: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[int] = None
    year: Optional[int] = None
    quantity: Optional[int] = None
    available_quantity: Optional[int] = None

    class Config:
        from_attributes = True


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


class PageMeta(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    offset: int


class PaginatedBooksList(BaseModel):
    meta: PageMeta
    books: list[BookSchema]
