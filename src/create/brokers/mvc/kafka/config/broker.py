from pydantic import BaseModel


class Settings(BaseModel):
    bootstrap_servers: str = "broker:9092"
    client_id: str = "robyn-app"
    group_id: str = "robyn-app"
    topic_prefix: str = "app"
