from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserBriefSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class AuditSchema(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]

    created_by: Optional[UserBriefSchema] = None
    updated_by: Optional[UserBriefSchema] = None
    deleted_by: Optional[UserBriefSchema] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.astimezone(timezone.utc)
            .isoformat()
            .replace('+00:00', 'Z')
            if v
            else None
        },
    )
