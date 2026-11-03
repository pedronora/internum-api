from pydantic import BaseModel, EmailStr, validator

from internum.utils.validators import validate_password_complexity


class Token(BaseModel):
    access_token: str
    token_type: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    _validate_password = validator('new_password', allow_reuse=True)(
        validate_password_complexity
    )


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class Message(BaseModel):
    message: str
