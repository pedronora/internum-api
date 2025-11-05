from datetime import datetime
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
    )
