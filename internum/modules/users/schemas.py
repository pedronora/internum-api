from datetime import datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    validator,
)

from internum.modules.users.enums import Role, Setor

MIN_LENGTH_PWD = 8
MAX_LENGTH_PWD = 64


def validate_password_complexity(pwd: str) -> str:
    if len(pwd) < MIN_LENGTH_PWD or len(pwd) > MAX_LENGTH_PWD:
        raise ValueError('A senha deve ter entre 8 e 64 caracteres.')
    if not any(char.isdigit() for char in pwd):
        raise ValueError('A senha deve conter pelo menos um dígito.')
    if not any(char.islower() for char in pwd):
        raise ValueError('A senha deve conter pelo menos uma letra minúscula.')
    if not any(char.isupper() for char in pwd):
        raise ValueError('A senha deve conter pelo menos uma letra maiúscula.')
    if not any(not char.isalnum() for char in pwd):
        raise ValueError(
            'A senha deve conter pelo menos um caractere especial.'
        )
    return pwd


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
        return v  # pragma: no cover


class UserCreate(UserBase):
    password: str
    _validate_password = validator('password', allow_reuse=True)(
        validate_password_complexity
    )


class UserChangePassword(BaseModel):
    password: str
    _validate_password = validator('password', allow_reuse=True)(
        validate_password_complexity
    )


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
        return v  # pragma: no cover


class FilterPage(BaseModel):
    offset: int = Field(ge=0, default=0)
    limit: int = Field(ge=0, default=10)


class Message(BaseModel):
    message: str
