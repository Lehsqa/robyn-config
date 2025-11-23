from pydantic import BaseModel


class Settings(BaseModel):
    format: str = "{time:YYYY-MM-DD HH:mm:ss} | {level:<5} | {message}"
    file: str = "robyn_app"
    rotation: str = "10 MB"
    compression: str = "zip"
