from datetime import datetime
from typing import Annotated

from pydantic import Field

from .base import InternalEntity


class TimeStampMixin(InternalEntity):
    created_at: Annotated[datetime, Field(default_factory=datetime.utcnow)]
    updated_at: Annotated[datetime, Field(default_factory=datetime.utcnow)]
