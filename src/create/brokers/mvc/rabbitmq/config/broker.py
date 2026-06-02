from urllib.parse import quote

from pydantic import BaseModel


class Settings(BaseModel):
    host: str = "broker"
    port: int = 5672
    user: str = "app"
    password: str = "app"
    virtual_host: str = "/"
    exchange: str = "app.events"
    url: str | None = None

    @property
    def dsn(self) -> str:
        if self.url:
            return self.url
        virtual_host = quote(self.virtual_host, safe="")
        return (
            f"amqp://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{virtual_host}"
        )
