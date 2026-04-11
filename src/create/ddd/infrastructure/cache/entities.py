from datetime import datetime
from typing import Annotated, Generic, TypeVar

from pydantic import Field

from ..application import InternalEntity

_CacheEntryInstance = TypeVar("_CacheEntryInstance", bound=InternalEntity)


class CacheEntry(InternalEntity, Generic[_CacheEntryInstance]):
    instance: _CacheEntryInstance
    created_at: Annotated[datetime, Field(default_factory=datetime.utcnow)]
