from pydantic import BaseModel

from . import frontend as _frontend


class Settings(BaseModel):
    frontend: _frontend.Settings = _frontend.Settings()
