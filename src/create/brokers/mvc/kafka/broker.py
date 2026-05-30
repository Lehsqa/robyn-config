from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Mapping
from typing import Annotated, Any

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from pydantic import Field

from .config import settings
from .schemas import InternalEntity


class BrokerMessage(InternalEntity):
    topic: str
    payload: Any
    headers: Annotated[dict[str, str], Field(default_factory=dict)]


class MessageBroker:
    def __init__(self) -> None:
        self.producer: AIOKafkaProducer | None = None

    async def __aenter__(self) -> "MessageBroker":
        self.producer = AIOKafkaProducer(
            bootstrap_servers=settings.broker.bootstrap_servers,
            client_id=settings.broker.client_id,
        )
        await self.producer.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.producer is not None:
            await self.producer.stop()
        self.producer = None

    def _topic(self, topic: str) -> str:
        prefix = settings.broker.topic_prefix.strip()
        return f"{prefix}.{topic}" if prefix else topic

    def _encode(self, payload: Any) -> bytes:
        return json.dumps(payload).encode("utf-8")

    def _decode(self, payload: bytes) -> Any:
        return json.loads(payload.decode("utf-8"))

    def _headers(
        self, headers: Mapping[str, str] | None
    ) -> list[tuple[str, bytes]]:
        return [
            (key, value.encode("utf-8"))
            for key, value in dict(headers or {}).items()
        ]

    async def publish(
        self,
        topic: str,
        payload: Any,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if self.producer is None:
            raise RuntimeError("MessageBroker not initialized")

        await self.producer.send_and_wait(
            self._topic(topic),
            value=self._encode(payload),
            headers=self._headers(headers),
        )

    async def consume(
        self,
        topic: str,
        group_id: str | None = None,
    ) -> AsyncGenerator[BrokerMessage, None]:
        consumer = AIOKafkaConsumer(
            self._topic(topic),
            bootstrap_servers=settings.broker.bootstrap_servers,
            group_id=group_id or settings.broker.group_id,
        )
        await consumer.start()
        try:
            async for record in consumer:
                yield BrokerMessage(
                    topic=topic,
                    payload=self._decode(record.value),
                    headers={
                        key: value.decode("utf-8")
                        for key, value in (record.headers or [])
                    },
                )
        finally:
            await consumer.stop()
