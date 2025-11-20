from pydantic import BaseModel


class TokenSettings(BaseModel):
    secret_key: str = "dev-secret"
    ttl: int = 3600


class Settings(BaseModel):
    algorithm: str = "HS256"
    scheme: str = "Bearer"
    access_token: TokenSettings = TokenSettings(ttl=3600)
    refresh_token: TokenSettings = TokenSettings(ttl=86400)
    user_activation_ttl: int = 0
    password_reset_token_ttl: int = 0
    session_secret_key: str = "change-me"
