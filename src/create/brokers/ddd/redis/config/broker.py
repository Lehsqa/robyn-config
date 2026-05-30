from pydantic import BaseModel


class Settings(BaseModel):
    host: str = "broker"
    port: int = 6379
    db: int = 1
    topic_prefix: str = "app"
