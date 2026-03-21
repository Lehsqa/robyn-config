from robyn import Request, Response, Robyn

from ..utils import json_response


def register(app: Robyn) -> None:
    @app.get("/health", const=True, openapi_name="Health Check", openapi_tags=["Health"])
    async def health(_: Request) -> Response:
        """Returns the current health status of the application."""
        return json_response({"status": "ok"})
