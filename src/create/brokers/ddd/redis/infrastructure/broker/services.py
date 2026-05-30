from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Mapping
from typing import Any

from redis.asyncio import Redis

from ...config import settings
from .entities import BrokerMessage


class MessageBroker:
    def __init__(self) -> None:
        self.client: Redis | None = None

    async def __aenter__(self) -> "MessageBroker":
        self.client = Redis(
            host=settings.broker.host,
            port=settings.broker.port,
            db=settings.broker.db,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            await self.client.close()
        self.client = None

    def _topic(self, topic: str) -> str:
        prefix = settings.broker.topic_prefix.strip()
        return f"{prefix}.{topic}" if prefix else topic

    def _encode(
        self, payload: Any, headers: Mapping[str, str] | None
    ) -> bytes:
        return json.dumps(
            {"payload": payload, "headers": dict(headers or {})}
        ).encode("utf-8")

    def _decode(self, payload: bytes | str) -> dict[str, Any]:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        return json.loads(payload)

    async def publish(
        self,
        topic: str,
        payload: Any,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if self.client is None:
            raise RuntimeError("MessageBroker not initialized")
        await self.client.publish(
            self._topic(topic), self._encode(payload, headers)
        )

    async def consume(self, topic: str) -> AsyncGenerator[BrokerMessage, None]:
        if self.client is None:
            raise RuntimeError("MessageBroker not initialized")

        wire_topic = self._topic(topic)
        pubsub = self.client.pubsub()
        await pubsub.subscribe(wire_topic)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                envelope = self._decode(message["data"])
                yield BrokerMessage(
                    topic=topic,
                    payload=envelope["payload"],
                    headers=envelope.get("headers", {}),
                )
        finally:
            await pubsub.unsubscribe(wire_topic)
            close = getattr(pubsub, "aclose", pubsub.close)
            await close()
