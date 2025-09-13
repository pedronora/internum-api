from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from internum.modules.users.enums import Role, Setor


class UserBase(BaseModel):
    name: str
    username: str
    email: EmailStr
    setor: Setor
    subsetor: str
    role: Role = Role.USER
    active: bool = True


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class UserList(BaseModel):
    users: list[UserRead]


class FilterPage(BaseModel):
    offset: int = Field(ge=0, default=0)
    limit: int = Field(ge=0, default=10)
