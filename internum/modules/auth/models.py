from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from internum.core.models.registry import table_registry


@table_registry.mapped_as_dataclass
class PasswordResetToken:
    __tablename__ = 'password_reset_tokens'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)

    def is_expired(self):
        return datetime.now(UTC) > self.expires_at


@table_registry.mapped_as_dataclass
class RefreshToken:
    __tablename__ = 'refresh_tokens'

    jti: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id', ondelete='CASCADE'),
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    session_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    rotated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.timezone('UTC', func.now()),
        init=False,
    )

    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    def is_session_expired(self, max_days: int) -> bool:
        return datetime.now(UTC) >= self.session_started_at + timedelta(
            days=max_days
        )
