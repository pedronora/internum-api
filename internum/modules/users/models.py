from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internum.core.models.registry import table_registry
from internum.modules.users.enums import Role, Unidade

# ruff: noqa: F821


@table_registry.mapped_as_dataclass
class User:
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    name: Mapped[str]
    username: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str]
    cpf: Mapped[str] = mapped_column(String(11), nullable=False, unique=True)
    birthday: Mapped[date] = mapped_column(Date)
    email: Mapped[str] = mapped_column(unique=True)
    unidade: Mapped[Unidade] = mapped_column(
        SqlEnum(Unidade, name='unidade_enum'), nullable=False
    )

    hiring_date: Mapped[date] = mapped_column(Date, nullable=False)
    termination_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, init=False
    )

    subunidade: Mapped[str | None] = mapped_column(
        String(80), nullable=True, default=None
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None
    )
    gross_salary: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True, default=None
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    role_assignments: Mapped[list['UserRole']] = relationship(
        back_populates='user',
        foreign_keys='UserRole.user_id',
        cascade='all, delete-orphan',
        lazy='selectin',
        init=False,
    )

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

    @property
    def roles(self) -> list[Role]:
        return [assignment.role for assignment in self.role_assignments]

    def terminate(self, date: date):
        self.termination_date = date
        self.active = False


@table_registry.mapped_as_dataclass
class UserRole:
    __tablename__ = 'user_roles'
    __table_args__ = (
        UniqueConstraint('user_id', 'role', name='uq_user_roles_user_role'),
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    role: Mapped[Role] = mapped_column(
        SqlEnum(Role, name='role_enum'), nullable=False
    )
    granted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        default=None,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.timezone('UTC', func.now()),
        init=False,
    )

    user: Mapped['User'] = relationship(
        back_populates='role_assignments',
        foreign_keys=[user_id],
        init=False,
    )
    granted_by: Mapped['User'] = relationship(
        foreign_keys=[granted_by_id], init=False
    )
