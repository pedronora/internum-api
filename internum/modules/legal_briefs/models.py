from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internum.core.models.mixins import AuditMixin
from internum.core.models.registry import table_registry

# ruff: noqa: F821


@table_registry.mapped_as_dataclass
class LegalBrief(AuditMixin):
    __tablename__ = 'legal_briefs'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text, nullable=False)

    canceled: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id'), nullable=True, default=None
    )
    canceled_by: Mapped['User'] = relationship(
        foreign_keys=[canceled_by_id],
        init=False,
    )
    canceled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        init=False,
    )

    revisions: Mapped[list['LegalBriefRevision']] = relationship(
        back_populates='brief',
        order_by='desc(LegalBriefRevision.created_at)',
        cascade='all, delete-orphan',
        lazy='selectin',
        init=False,
    )


@table_registry.mapped_as_dataclass
class LegalBriefRevision(AuditMixin):
    __tablename__ = 'legal_brief_revisions'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    brief_id: Mapped[int] = mapped_column(
        ForeignKey('legal_briefs.id'), nullable=False
    )
    brief: Mapped['LegalBrief'] = relationship(
        back_populates='revisions',
        init=False,
    )

    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
