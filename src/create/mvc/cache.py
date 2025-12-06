from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Generic, TypeVar, get_args

from pydantic import Field
from redis.asyncio import Redis

from .config import settings
from .schemas import InternalEntity
from .utils import NotFoundError

try:  # Optional dependency for fakeredis in dev
    from fakeredis.aioredis import FakeRedis, FakeServer  # type: ignore
except Exception:  # pragma: no cover - fakeredis not installed
    FakeRedis = None  # type: ignore
    FakeServer = None  # type: ignore

CacheClient = Redis

_fake_server: "FakeServer | None" = None
_CacheEntryInstance = TypeVar("_CacheEntryInstance", bound=InternalEntity)


class CacheEntry(InternalEntity, Generic[_CacheEntryInstance]):
    instance: _CacheEntryInstance
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CacheRepository(Generic[_CacheEntryInstance]):
    def __init__(self) -> None:
        self.redis_client: CacheClient | None = None

    async def __aenter__(self) -> "CacheRepository[_CacheEntryInstance]":
        if settings.cache.use_fake:
            if (
                not FakeRedis or not FakeServer
            ):  # pragma: no cover - import guard
                raise RuntimeError(
                    "fakeredis must be installed to use the fake cache "
                    "(SETTINGS__CACHE__USE_FAKE=true). Install the `[dev]` extras "
                    "or disable the flag."
                )
            global _fake_server
            if _fake_server is None:
                _fake_server = FakeServer()
            self.redis_client = FakeRedis(server=_fake_server)
        else:
            self.redis_client = Redis(
                host=settings.cache.host,
                port=settings.cache.port,
                db=settings.cache.db,
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.redis_client is not None:
            await self.redis_client.close()
        self.redis_client = None

    def _build_key(self, namespace: str, key: Any) -> str:
        return f"{namespace}:{key}"

    def _model_for_entry(self) -> type[_CacheEntryInstance]:
        try:
            return get_args(self.__orig_class__)[0]  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - fallback
            return InternalEntity  # type: ignore[return-value]

    async def get(
        self, namespace: str, key: Any
    ) -> CacheEntry[_CacheEntryInstance]:
        if self.redis_client is None:
            raise RuntimeError("CacheRepository not initialized")

        built_key = self._build_key(namespace, key)
        raw = await self.redis_client.get(built_key)
        if raw is None:
            raise NotFoundError(message=f"Cache entry not found. Key: {key}")

        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError) as exc:  # pragma: no cover
            raise NotFoundError(
                message=f"Cache entry invalid. Key: {key}"
            ) from exc

        model = self._model_for_entry()
        return CacheEntry[_CacheEntryInstance](
            instance=model(**payload["instance"])
        )

    async def set(
        self,
        *,
        namespace: str,
        key: Any,
        instance: _CacheEntryInstance,
        ttl: int | None = None,
    ) -> CacheEntry[_CacheEntryInstance]:
        if self.redis_client is None:
            raise RuntimeError("CacheRepository not initialized")

        entry = CacheEntry[_CacheEntryInstance](instance=instance)
        await self.redis_client.set(
            name=self._build_key(namespace, key),
            value=entry.model_dump_json(),
            ex=ttl,
        )
        return entry

    async def delete(self, namespace: str, key: Any) -> None:
        if self.redis_client is None:
            raise RuntimeError("CacheRepository not initialized")
        await self.redis_client.delete(self._build_key(namespace, key))
