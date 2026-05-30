from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Mapping
from typing import Annotated, Any

import aio_pika
from aio_pika.abc import (
    AbstractExchange,
    AbstractRobustChannel,
    AbstractRobustConnection,
)
from pydantic import Field

from .config import settings
from .schemas import InternalEntity


class BrokerMessage(InternalEntity):
    topic: str
    payload: Any
    headers: Annotated[dict[str, str], Field(default_factory=dict)]


class MessageBroker:
    def __init__(self) -> None:
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractRobustChannel | None = None
        self.exchange: AbstractExchange | None = None

    async def __aenter__(self) -> "MessageBroker":
        self.connection = await aio_pika.connect_robust(settings.broker.dsn)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            settings.broker.exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.connection is not None:
            await self.connection.close()
        self.connection = None
        self.channel = None
        self.exchange = None

    def _encode(
        self, payload: Any, headers: Mapping[str, str] | None
    ) -> bytes:
        return json.dumps(
            {"payload": payload, "headers": dict(headers or {})}
        ).encode("utf-8")

    def _decode(self, payload: bytes) -> dict[str, Any]:
        return json.loads(payload.decode("utf-8"))

    async def publish(
        self,
        topic: str,
        payload: Any,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        if self.exchange is None:
            raise RuntimeError("MessageBroker not initialized")

        message = aio_pika.Message(
            body=self._encode(payload, headers),
            content_type="application/json",
            headers=dict(headers or {}),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.exchange.publish(message, routing_key=topic)

    async def consume(
        self,
        queue_name: str,
        routing_key: str = "#",
    ) -> AsyncGenerator[BrokerMessage, None]:
        if self.channel is None or self.exchange is None:
            raise RuntimeError("MessageBroker not initialized")

        queue = await self.channel.declare_queue(queue_name, durable=True)
        await queue.bind(self.exchange, routing_key=routing_key)
        async with queue.iterator() as iterator:
            async for message in iterator:
                async with message.process():
                    envelope = self._decode(message.body)
                    yield BrokerMessage(
                        topic=message.routing_key,
                        payload=envelope["payload"],
                        headers=envelope.get("headers", {}),
                    )
