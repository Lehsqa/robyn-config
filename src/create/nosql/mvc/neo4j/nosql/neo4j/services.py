from __future__ import annotations

from neo4j import AsyncDriver, AsyncGraphDatabase

from ...config import settings


class NoSQLService:
    def __init__(self) -> None:
        self.driver: AsyncDriver | None = None

    async def __aenter__(self) -> "NoSQLService":
        self.driver = AsyncGraphDatabase.driver(
            settings.nosql.neo4j.uri,
            auth=(settings.nosql.neo4j.user, settings.nosql.neo4j.password),
        )
        await self.driver.verify_connectivity()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.driver is not None:
            await self.driver.close()
        self.driver = None
