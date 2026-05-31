from __future__ import annotations

from pymongo import AsyncMongoClient

from ...config import settings


class NoSQLService:
    def __init__(self) -> None:
        self.client: AsyncMongoClient | None = None

    async def __aenter__(self) -> "NoSQLService":
        self.client = AsyncMongoClient(settings.nosql.mongodb.dsn)
        await self.client.admin.command("ping")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            await self.client.close()
        self.client = None
