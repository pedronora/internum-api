from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    email: Mapped[str] = mapped_column(unique=True)
    setor: Mapped[Setor] = mapped_column(
        SqlEnum(Setor, name='setor_enum'), nullable=False
    )
    subsetor: Mapped[str] = mapped_column(nullable=False)
    notices: Mapped[list['Notice']] = relationship(
        back_populates='user', cascade='all, delete-orphan', init=False
    )

    reads: Mapped[list['NoticeRead']] = relationship(
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='selectin',
        init=False,
    )
    legal_briefs: Mapped[list['LegalBrief']] = relationship(
        back_populates='created_by',
        cascade='all, delete-orphan',
        init=False,
        lazy='selectin',
        foreign_keys='LegalBrief.created_by_id',
    )
    revisions: Mapped[list['LegalBriefRevision']] = relationship(
        back_populates='updated_by',
        init=False,
        lazy='selectin',
    )
    role: Mapped[Role] = mapped_column(
        SqlEnum(Role, name='role_enum'), default=Role.USER, nullable=False
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        init=False, onupdate=func.now(), nullable=True
    )
