from pydantic import BaseModel


class Status(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    status_code: int
    detail: str
