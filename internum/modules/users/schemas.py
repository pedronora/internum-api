from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from internum.modules.users.enums import Role, Setor


class UserBase(BaseModel):
    name: str
    username: str
    email: EmailStr
    setor: Setor
    subsetor: str
    role: Role = Role.USER
    active: bool = True

    @field_validator('email', mode='before')
    def normalize_email(cls, v):
        if v and isinstance(v, str):
            return v.strip().lower()
        return v


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class UserList(BaseModel):
    users: list[UserRead]


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=4)
    username: Optional[str] = Field(None, min_length=4)
    email: Optional[EmailStr] = None
    setor: Optional[Setor] = None
    subsetor: Optional[str] = Field(None, min_length=4)
    role: Optional[Role] = None
    active: Optional[bool] = None

    @field_validator('email', mode='before')
    def normalize_email(cls, v):
        if v and isinstance(v, str):
            return v.strip().lower()
        return v


class FilterPage(BaseModel):
    offset: int = Field(ge=0, default=0)
    limit: int = Field(ge=0, default=10)
