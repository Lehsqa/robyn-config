from robyn import Request, Response, Robyn

from ..utils import json_response


def register(app: Robyn) -> None:
    @app.get("/health", const=True)
    async def health(_: Request) -> Response:
        return json_response({"status": "ok"})
