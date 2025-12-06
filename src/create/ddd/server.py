import logging
from pathlib import Path

from app.config import settings
from app.infrastructure.application import error_response, middlewares
from app.infrastructure.application.factory import create
from app.operational.authentication import JWTAuthenticationHandler
from app.presentation import register_routes
from loguru import logger
from robyn import Robyn

log_path = Path(settings.root_dir) / "logs"
log_path.mkdir(exist_ok=True)
logger.add(
    log_path / f"{settings.logging.file}.log",
    format=settings.logging.format,
    rotation=settings.logging.rotation,
    compression=settings.logging.compression,
    level="INFO",
)

if not settings.debug:
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.WARNING)

app: Robyn = create(
    __name__,
    route_registrars=(register_routes,),
    middlewares=(
        middlewares.sessions.register,
        middlewares.cors.register,
    ),
    exception_handler=error_response,
    authentication_handler=JWTAuthenticationHandler(),
)


if __name__ == "__main__":
    app.start(host="0.0.0.0", port=8000)
