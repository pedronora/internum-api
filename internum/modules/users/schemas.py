from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import Query
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
    validator,
)

from internum.core.authorization import Permission
from internum.modules.users.enums import Role, Unidade
from internum.utils.validators import validate_password_complexity

CPF_LENGTH = 11
CPF_FIRST_WEIGHT = 10
CPF_SECOND_WEIGHT = 11
CPF_DIGIT_LIMIT = 10
CPF_BASE_LENGTH = 9
MIN_PHONE_DIGITS = 10
MAX_PHONE_DIGITS = 13


def validate_cpf(cpf: str) -> str:
    digits = ''.join(char for char in cpf if char.isdigit())

    if len(digits) != CPF_LENGTH:
        raise ValueError('CPF deve conter 11 dígitos.')

    if digits == digits[0] * CPF_LENGTH:
        raise ValueError('CPF inválido.')

    first_sum = sum(
        int(digits[i]) * (CPF_FIRST_WEIGHT - i) for i in range(CPF_BASE_LENGTH)
    )
    first_digit = (first_sum * CPF_DIGIT_LIMIT) % CPF_LENGTH
    first_digit = 0 if first_digit == CPF_DIGIT_LIMIT else first_digit

    second_sum = sum(
        int(digits[i]) * (CPF_SECOND_WEIGHT - i)
        for i in range(CPF_FIRST_WEIGHT)
    )
    second_digit = (second_sum * CPF_DIGIT_LIMIT) % CPF_LENGTH
    second_digit = 0 if second_digit == CPF_DIGIT_LIMIT else second_digit

    if digits[CPF_BASE_LENGTH] != str(first_digit) or digits[
        CPF_FIRST_WEIGHT
    ] != str(second_digit):
        raise ValueError('CPF inválido.')

    return digits


def validate_phone(phone: str) -> str | None:
    if not phone or not phone.strip():
        return None

    digits = ''.join(char for char in phone if char.isdigit())

    if not MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS:
        raise ValueError(
            'Telefone deve conter entre 10 e 13 dígitos (DD + número).'
        )

    return digits


class UserBase(BaseModel):
    name: str
    username: str
    cpf: str
    email: EmailStr
    birthday: date
    hiring_date: date
    unidade: Unidade
    subunidade: Optional[str] = None
    active: bool = True
    phone: Optional[str] = None
    gross_salary: Optional[Decimal] = Field(None, ge=0)

    @field_validator('email', mode='before')
    def normalize_email(cls, v):
        if v and isinstance(v, str):
            return v.strip().lower()
        return v  # pragma: no cover

    @field_validator('name', 'username', mode='before')
    def strip_whitespace(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v  # pragma: no cover

    @field_validator('cpf', mode='before')
    def validate_and_normalize_cpf(cls, v):
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError('CPF inválido.')
        return validate_cpf(v)

    @field_validator('phone', mode='before')
    def validate_and_normalize_phone(cls, v):
        if v is None or not v:
            return None
        if not isinstance(v, str):
            raise ValueError('Telefone inválido.')
        return validate_phone(v)


class UserCreate(UserBase):
    password: str
    roles: list[Role] = Field(min_length=1)

    _validate_password = validator('password', allow_reuse=True)(
        validate_password_complexity
    )


class UserChangePassword(BaseModel):
    old_password: str
    new_password: str
    _validate_password = validator('new_password', allow_reuse=True)(
        validate_password_complexity
    )


class UserRead(UserBase):
    id: int
    roles: list[Role]
    termination_date: date | None = None
    created_at: datetime
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class UserSelf(UserRead):
    permissions: list[Permission] = Field(default_factory=list)


class UserPublic(BaseModel):
    id: int
    name: str
    username: str
    email: EmailStr
    unidade: Unidade
    subunidade: Optional[str] = None
    phone: Optional[str] = None
    roles: list[Role]

    model_config = ConfigDict(from_attributes=True)


class PageMeta(BaseModel):
    total: int
    page: int
    size: int
    total_pages: int
    has_next: bool
    has_prev: bool
    offset: int


class PaginatedUserList(BaseModel):
    meta: PageMeta
    users: list[UserRead]


class PaginatedUserDirectory(BaseModel):
    meta: PageMeta
    users: list[UserPublic]


class UserUpdate(UserBase):
    name: Optional[str] = Field(None, min_length=4)
    username: Optional[str] = Field(None, min_length=4)
    cpf: Optional[str] = None
    email: Optional[EmailStr] = None
    birthday: Optional[date] = None
    hiring_date: Optional[date] = None
    unidade: Optional[Unidade] = None
    subunidade: Optional[str] = Field(None, min_length=2)
    active: Optional[bool] = None
    phone: Optional[str] = None
    gross_salary: Optional[Decimal] = Field(None, ge=0)
    termination_date: Optional[date] = None
    roles: Optional[list[Role]] = Field(None, min_length=1)

    @model_validator(mode='after')
    def validate_active_termination_date(self):
        if self.active is True and self.termination_date is not None:
            raise ValueError(
                'termination_date deve ser nulo quando active for true.'
            )
        return self


class UserQueryParams(BaseModel):
    limit: int = Query(
        default=10, ge=1, description='Número de itens por página'
    )
    offset: int = Query(default=0, ge=0, description='Número de itens a pular')

    search: Optional[str] = Query(
        default=None,
        min_length=1,
        description='Termo de busca para os campos: name, username, email',
    )


class Message(BaseModel):
    message: str


class ChangePasswordResponse(Message):
    access_token: str
