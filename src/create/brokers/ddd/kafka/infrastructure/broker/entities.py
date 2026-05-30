from typing import Annotated, Any

from pydantic import Field

from ..application import InternalEntity


class BrokerMessage(InternalEntity):
    topic: str
    payload: Any
    headers: Annotated[dict[str, str], Field(default_factory=dict)]
