from robyn import Request, Response, Robyn

from ..infrastructure.application import JSON_HEADERS


def register(app: Robyn) -> None:
    @app.get(
        "/health",
        const=True,
        openapi_name="Health Check",
        openapi_tags=["Health"],
    )
    async def health(_: Request) -> Response:
        """Returns the current health status of the application."""
        return Response(200, JSON_HEADERS, b'{"status":"ok"}')
