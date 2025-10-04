from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internum.core.models.registry import table_registry

# ruff: noqa: F821


@table_registry.mapped_as_dataclass
class Notice:
    __tablename__ = 'notices'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    content: Mapped[str]

    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'), nullable=False
    )

    user: Mapped['User'] = relationship(back_populates='notices', init=False)

    reads: Mapped[list['NoticeRead']] = relationship(
        back_populates='notice',
        cascade='all, delete-orphan',
        lazy='selectin',
        init=False,
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )

    @hybrid_property
    def reads_count(self) -> int:
        return len(self.reads)


@table_registry.mapped_as_dataclass
class NoticeRead:
    __tablename__ = 'notice_reads'
    __table_args__ = (
        UniqueConstraint('user_id', 'notice_id', name='uq_notice_user_read'),
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'), nullable=False
    )
    notice_id: Mapped[int] = mapped_column(
        ForeignKey('notices.id'), nullable=False
    )

    read_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )

    user: Mapped['User'] = relationship(back_populates='reads', init=False)
    notice: Mapped['Notice'] = relationship(back_populates='reads', init=False)
