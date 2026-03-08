from __future__ import annotations

from typing import Any

from ..auth import authenticate_credentials
from .auth_core import register_auth_routes as register_auth_routes_core


def register_auth_routes(site: Any) -> None:
    register_auth_routes_core(
        site,
        authenticate_user=authenticate_credentials,
    )
