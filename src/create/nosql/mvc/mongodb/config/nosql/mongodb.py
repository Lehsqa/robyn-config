from urllib.parse import quote_plus

from pydantic import BaseModel


class Settings(BaseModel):
    host: str = "mongodb"
    port: int = 27017
    user: str = "app"
    password: str = "app"
    database: str = "app"
    auth_source: str = "admin"
    url: str | None = None

    @property
    def dsn(self) -> str:
        if self.url:
            return self.url
        user = quote_plus(self.user)
        password = quote_plus(self.password)
        database = quote_plus(self.database)
        auth_source = quote_plus(self.auth_source)
        return (
            f"mongodb://{user}:{password}@{self.host}:{self.port}/{database}"
            f"?authSource={auth_source}"
        )
