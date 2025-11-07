from datetime import datetime
from typing import Optional

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserPublic(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class LegalBriefCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

    @field_validator('title', 'content', mode='before')
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v  # pragma: no cover


class LegalBriefUpdate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

    @field_validator('title', 'content', mode='before')
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v  # pragma: no cover


class LegalBriefRevisionSchema(BaseModel):
    id: int
    brief_id: int
    title: str
    content: str
    updated_by: UserPublic
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LegalBriefSchema(BaseModel):
    id: int
    title: str
    content: str

    created_by: UserPublic
    created_at: datetime

    updated_by: Optional[UserPublic] = None
    updated_at: Optional[datetime] = None

    canceled: bool
    canceled_by: Optional[UserPublic] = None

    revisions: list['LegalBriefRevisionSchema']

    model_config = ConfigDict(from_attributes=True)


class PageMeta(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    offset: int


class PaginatedLegalBriefList(BaseModel):
    meta: PageMeta
    legal_briefs: list[LegalBriefSchema]


class LegalBriefQueryParams(BaseModel):
    limit: int = Query(
        default=10, ge=1, description='Number of items per page'
    )
    offset: int = Query(default=0, ge=0, description='Number of items to skip')

    search: Optional[str] = Query(
        default=None,
        min_length=1,
        description='Search query for: title, content, user',
    )
