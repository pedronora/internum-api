from datetime import datetime

from pydantic import BaseModel


class Status(BaseModel):
    status: str
    version_db: str
    current_db: str
    current_time: datetime


class ErrorResponse(BaseModel):
    status_code: int
    detail: str
