from datetime import datetime

from pydantic import Field

from .base import InternalEntity


class TimeStampMixin(InternalEntity):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
