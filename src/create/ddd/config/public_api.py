from pydantic import BaseModel


class DocsSettings(BaseModel):
    docs: str = "/docs"
    redoc: str = "/redoc"


class Settings(BaseModel):
    domain: str = "http://backend.local"
    name: str = "Robyn Quick"
    version: str = "0.1.0"
    urls: DocsSettings = DocsSettings()
