from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from internum.core.models.registry import table_registry

# ruff: noqa: F821


@table_registry.mapped_as_dataclass
class LegalBrief:
    __tablename__ = 'legal_briefs'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    title: Mapped[str]
    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_by_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'), nullable=False
    )
    created_by: Mapped['User'] = relationship(
        foreign_keys=[created_by_id],
        back_populates='legal_briefs',
        init=False,
    )

    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id'), nullable=True, default=None
    )
    updated_by: Mapped['User'] = relationship(
        foreign_keys=[updated_by_id],
        init=False,
    )

    canceled: Mapped[bool] = mapped_column(Boolean, default=False)
    canceled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey('users.id'), nullable=True, default=None
    )
    canceled_by: Mapped['User'] = relationship(
        foreign_keys=[canceled_by_id],
        init=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        init=False, onupdate=func.now(), nullable=True
    )

    revisions: Mapped[list['LegalBriefRevision']] = relationship(
        back_populates='brief',
        order_by='desc(LegalBriefRevision.created_at)',
        cascade='all, delete-orphan',
        lazy='selectin',
        init=False,
    )


@table_registry.mapped_as_dataclass
class LegalBriefRevision:
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
    updated_by_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'), nullable=False
    )
    updated_by: Mapped['User'] = relationship(
        foreign_keys=[updated_by_id],
        init=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        init=False, server_default=func.now()
    )
