from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BirthdayUser(BaseModel):
    id: int
    name: str
    birthday: date

    model_config = ConfigDict(from_attributes=True)


class LegalBriefRandom(BaseModel):
    id: int
    title: str
    content: str

    model_config = ConfigDict(from_attributes=True)


class UnreadNotice(BaseModel):
    id: int
    title: str
    content: str

    model_config = ConfigDict(from_attributes=True)


class UnreadNoticesSummary(BaseModel):
    total: int
    unread_notices: list[UnreadNotice]

    model_config = ConfigDict(from_attributes=True)


class BookBriefSchema(BaseModel):
    id: int
    title: str

    model_config = ConfigDict(from_attributes=True)


class LoansByUser(BaseModel):
    id: int
    book: BookBriefSchema
    due_date: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class HomeSummary(BaseModel):
    current_month: str
    birthdays: list[BirthdayUser]
    legal_brief: Optional[LegalBriefRandom] = None
    unread_notices: UnreadNoticesSummary
    loans: list[LoansByUser]
