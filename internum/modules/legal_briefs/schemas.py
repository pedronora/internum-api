from datetime import datetime
from typing import List, Optional

from fastapi import Query
from pydantic import BaseModel, Field


class UserPublic(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class LegalBriefCreate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class LegalBriefUpdate(BaseModel):
    title: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


class LegalBriefRevisionSchema(BaseModel):
    id: int
    brief_id: int
    title: str
    content: str
    updated_by: UserPublic
    created_at: datetime

    class Config:
        from_attributes = True


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

    revisions: Optional[List['LegalBriefRevisionSchema']] = None

    class Config:
        from_attributes = True


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
