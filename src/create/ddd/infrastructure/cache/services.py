from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Generic, TypeVar, get_args

from redis.asyncio import Redis
from redis.asyncio.client import Pipeline

from ...config import settings
from ..application import InternalEntity, NotFoundError
from .entities import CacheEntry

if TYPE_CHECKING:
    from fakeredis.aioredis import FakeRedis  # pragma: no cover
    from fakeredis.aioredis import FakeServer  # pragma: no cover

    CacheClient = Redis | FakeRedis
else:
    CacheClient = Redis  # type: ignore[assignment]

_fake_server: "FakeServer" | None = None

_CacheEntryInstance = TypeVar("_CacheEntryInstance", bound=InternalEntity)


class CacheRepository(Generic[_CacheEntryInstance]):
    def __init__(self) -> None:
        self.redis_client: CacheClient | None = None
        self.transaction: Pipeline | None = None

    async def __aenter__(self) -> "CacheRepository[_CacheEntryInstance]":
        if settings.cache.use_fake:
            try:
                from fakeredis.aioredis import FakeRedis, FakeServer
            except ImportError as exc:
                raise RuntimeError(
                    "fakeredis must be installed to use the fake cache (SETTINGS__CACHE__USE_FAKE=true);"
                    " install the `[dev]` extras or disable the flag."
                ) from exc
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

        assert self.redis_client is not None
        self.transaction = self.redis_client.pipeline(transaction=True)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        assert self.redis_client is not None
        assert self.transaction is not None
        if exc_type is None:
            await self.transaction.execute()
        await self.redis_client.close()
        self.redis_client = None
        self.transaction = None

    def _build_key(self, namespace: str, key: Any) -> str:
        return f"{namespace}:{key}"

    async def get(
        self, namespace: str, key: Any
    ) -> CacheEntry[_CacheEntryInstance]:
        assert self.transaction is not None
        built_key = self._build_key(namespace, key)
        results = await self.transaction.get(built_key).execute()  # type: ignore[union-attr]
        if not results or results[0] is None:
            raise NotFoundError(message=f"Cache entry not found. Key: {key}")

        try:
            payload = json.loads(results[0])
        except (TypeError, json.JSONDecodeError) as exc:  # pragma: no cover
            raise NotFoundError(
                message=f"Cache entry invalid. Key: {key}"
            ) from exc

        struct = get_args(self.__orig_class__)[0]  # type: ignore[attr-defined]
        return CacheEntry[_CacheEntryInstance](
            instance=struct(**payload["instance"])
        )

    async def set(
        self,
        *,
        namespace: str,
        key: Any,
        instance: _CacheEntryInstance,
        ttl: int | None = None,
    ) -> CacheEntry[_CacheEntryInstance]:
        assert self.transaction is not None
        entry = CacheEntry[_CacheEntryInstance](instance=instance)
        await self.transaction.set(
            name=self._build_key(namespace, key),
            value=entry.model_dump_json(),
            ex=ttl,
        ).execute()  # type: ignore[union-attr]
        return entry

    async def delete(self, namespace: str, key: Any) -> None:
        assert self.transaction is not None
        await self.transaction.delete(self._build_key(namespace, key)).execute()  # type: ignore[union-attr]
