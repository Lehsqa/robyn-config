import logging
from pathlib import Path

from app.config import settings
from app.middlewares import cors, sessions
from app.urls import register_routes
from app.utils import error_response
from app.views.authentication import JWTAuthenticationHandler
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

app = Robyn(__file__)

# Configure app
app.exception(error_response)
app.configure_authentication(JWTAuthenticationHandler())

# Middlewares
sessions.register(app)
cors.register(app)

# Register routes
register_routes(app)

if __name__ == "__main__":
    app.start(host="0.0.0.0", port=8000)
