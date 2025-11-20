"""Application settings inspired by src 2 design."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from . import authentication as _authentication
from . import cache as _cache
from . import core
from . import cors as _cors
from . import database as _database
from . import integrations as _integrations
from . import logging as _logging
from . import mailing as _mailing
from . import public_api as _public_api

__all__ = ("settings", "Settings")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SETTINGS__",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    # infrastructure
    database: _database.Settings = _database.Settings()
    cache: _cache.Settings = _cache.Settings()

    # platform
    root_dir: Path
    src_dir: Path
    debug: bool = True
    public_api: _public_api.Settings = _public_api.Settings()
    logging: _logging.Settings = _logging.Settings()
    mailing: _mailing.Settings = _mailing.Settings()
    authentication: _authentication.Settings = _authentication.Settings()
    cors: _cors.Settings = _cors.Settings()

    # integrations
    integrations: _integrations.Settings = _integrations.Settings()


settings = Settings(root_dir=core.ROOT_PATH, src_dir=core.SRC_PATH)
