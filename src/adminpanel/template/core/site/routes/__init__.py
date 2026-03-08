from __future__ import annotations

from typing import Any

from .auth import register_auth_routes
from .dashboard import register_dashboard_routes
from .io import register_io_routes
from .models import register_model_view_routes
from .mutations import register_model_mutation_routes


def setup_routes(site: Any) -> None:
    register_dashboard_routes(site)
    register_auth_routes(site)
    register_model_view_routes(site)
    register_model_mutation_routes(site)
    register_io_routes(site)
