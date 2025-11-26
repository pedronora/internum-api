from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from internum.core.models.registry import table_registry


@table_registry.mapped_as_dataclass
class PasswordResetToken:
    __tablename__ = 'password_reset_tokens'

    id: Mapped[int] = mapped_column(init=False, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Integer, default=False)

    def is_expired(self):
        return datetime.now(UTC) > self.expires_at
