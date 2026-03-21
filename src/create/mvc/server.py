import logging
import sys
from pathlib import Path

from app.config import settings
from app.middlewares import cors, sessions
from app.urls import register_routes
from app.utils import error_response
from app.views.authentication import JWTAuthenticationHandler
from loguru import logger
from robyn import Robyn
from robyn.openapi import Components, OpenAPI, OpenAPIInfo

logger.remove()
logger.add(
    sys.stderr,
    format=settings.logging.format,
    level="INFO",
)

if settings.logging.file:
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

app = Robyn(
    __file__,
    openapi=OpenAPI(
        info=OpenAPIInfo(
            title=settings.public_api.name,
            version=settings.public_api.version,
            components=Components(
                securitySchemes={
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    }
                }
            ),
        ),
    ),
)

app.openapi.openapi_spec["security"] = [{"BearerAuth": []}]

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
