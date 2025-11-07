from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, Field, field_validator


class UserPublic(BaseModel):
    id: int
    name: str


class NoticeCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

    @field_validator('title', 'content', mode='before')
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v  # pragma: no cover


class NoticeReadSchema(BaseModel):
    user: UserPublic
    read_at: datetime


class NoticeSchema(NoticeCreate):
    id: int
    active: bool
    author: UserPublic = Field(
        ..., validation_alias='user', serialization_alias='author'
    )
    created_at: datetime
    reads_count: int = 0


class NoticeDetail(NoticeSchema):
    reads: list[NoticeReadSchema]


class PageMeta(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    offset: int


class PaginatedNoticeList(BaseModel):
    meta: PageMeta
    notices: list[NoticeSchema]


class NoticeQueryParams(BaseModel):
    limit: int = Query(
        default=10, ge=1, description='Number of items per page'
    )
    offset: int = Query(default=0, ge=0, description='Number of items to skip')

    search: Optional[str] = Query(
        default=None,
        min_length=1,
        description='Search query for: title, content, user',
    )


class Message(BaseModel):
    message: str
