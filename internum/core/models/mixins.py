from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

# ruff: noqa: F821


class AuditMixin:
    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            init=False,
            server_default=func.now(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls) -> Mapped[Optional[datetime]]:
        return mapped_column(
            init=False,
            onupdate=func.now(),
            nullable=True,
        )

    @declared_attr
    def deleted_at(cls) -> Mapped[Optional[datetime]]:
        return mapped_column(
            init=False,
            nullable=True,
        )

    @declared_attr
    def created_by_id(cls) -> Mapped[Optional[int]]:
        return mapped_column(
            ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            init=False,
        )

    @declared_attr
    def updated_by_id(cls) -> Mapped[Optional[int]]:
        return mapped_column(
            ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            init=False,
        )

    @declared_attr
    def deleted_by_id(cls) -> Mapped[Optional[int]]:
        return mapped_column(
            ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
            init=False,
        )

    @declared_attr
    def created_by(cls) -> Mapped[Optional['User']]:
        return relationship(
            'User',
            foreign_keys=[cls.created_by_id],
            lazy='joined',
            init=False,
        )

    @declared_attr
    def updated_by(cls) -> Mapped[Optional['User']]:
        return relationship(
            'User',
            foreign_keys=[cls.updated_by_id],
            lazy='joined',
            init=False,
        )

    @declared_attr
    def deleted_by(cls) -> Mapped[Optional['User']]:
        return relationship(
            'User',
            foreign_keys=[cls.deleted_by_id],
            lazy='joined',
            init=False,
        )

    def soft_delete(self, user_id: Optional[int] = None):
        """Marca o objeto como deletado e registra quem deletou."""
        self.deleted_at = datetime.utcnow()
        if user_id:
            self.deleted_by_id = user_id

    def mark_updated(self, user_id: Optional[int] = None):
        """Atualiza updated_by_id quando o objeto é modificado."""
        if user_id:
            self.updated_by_id = user_id
