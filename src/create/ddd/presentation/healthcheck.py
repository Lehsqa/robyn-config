from robyn import Request, Response, Robyn

from ..infrastructure.application import JSON_HEADERS


def register(app: Robyn) -> None:
    @app.get("/health", const=True)
    async def health(_: Request) -> Response:
        return Response(200, JSON_HEADERS, b'{"status":"ok"}')
