"""CORS middleware registration for Robyn (MVC template)."""

from typing import Sequence

from robyn import ALLOW_CORS, Robyn

from ..config import settings


def _normalize_sequence(values: Sequence[object] | None) -> list[str]:
    if values is None:
        return []
    return [str(value) for value in values]


def register(app: Robyn) -> None:
    origins_config = _normalize_sequence(settings.cors.allow_origins)
    headers_config = _normalize_sequence(settings.cors.allow_headers)

    origins: list[str] | str = origins_config or "*"
    if not headers_config or headers_config == ["*"]:
        headers: list[str] | str = "*"
    else:
        headers = headers_config

    ALLOW_CORS(app, origins=origins, headers=headers)
