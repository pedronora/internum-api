from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internum.core.models.mixins import AuditMixin
from internum.core.models.registry import table_registry

# ruff: noqa: F821


@table_registry.mapped_as_dataclass
class Notice(AuditMixin):
    __tablename__ = 'notices'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    content: Mapped[str]

    reads: Mapped[list['NoticeRead']] = relationship(
        back_populates='notice',
        cascade='all, delete-orphan',
        lazy='selectin',
        init=False,
    )

    active: Mapped[bool] = mapped_column(Boolean, default=True)

    @hybrid_property
    def reads_count(self) -> int:
        return len(self.reads)


@table_registry.mapped_as_dataclass
class NoticeRead(AuditMixin):
    __tablename__ = 'notice_reads'
    __table_args__ = (
        UniqueConstraint(
            'created_by_id', 'notice_id', name='uq_notice_user_read'
        ),
    )

    id: Mapped[int] = mapped_column(init=False, primary_key=True)

    notice_id: Mapped[int] = mapped_column(
        ForeignKey('notices.id'), nullable=False
    )

    notice: Mapped['Notice'] = relationship(back_populates='reads', init=False)
