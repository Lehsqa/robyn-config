from pydantic import BaseModel, EmailStr


class Settings(BaseModel):
    host: str = "localhost"
    port: int = 1025
    username: str | None = None
    password: str | None = None
    start_tls: bool = False
    sender_email: EmailStr = "no-reply@example.com"
    sender_name: str | None = "Robyn App"
