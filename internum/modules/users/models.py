from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from internum.core.models.registry import table_registry
from internum.modules.users.enums import Role, Setor

# ruff: noqa: F821


@table_registry.mapped_as_dataclass
class User:
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    cpf: Mapped[str] = mapped_column(String(11), nullable=False)
    birthday: Mapped[date] = mapped_column(Date)
    email: Mapped[str] = mapped_column(unique=True)
    setor: Mapped[Setor] = mapped_column(
        SqlEnum(Setor, name='setor_enum'), nullable=False
    )
    subsetor: Mapped[str] = mapped_column(nullable=False)

    hiring_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, init=False
    )

    role: Mapped[Role] = mapped_column(
        SqlEnum(Role, name='role_enum'), default=Role.USER, nullable=False
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.timezone('UTC', func.now()),
        init=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.timezone('UTC', func.now()),
        nullable=True,
        init=False,
    )

    def terminate(self, date: date):
        self.termination_date = date
        self.active = False
