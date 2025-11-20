from pydantic import BaseModel


class Settings(BaseModel):
    host: str = "cache"
    port: int = 6379
    db: int = 0
    use_fake: bool = True
    ttl_activation_seconds: int = 3600
    ttl_password_reset_seconds: int = 3600
