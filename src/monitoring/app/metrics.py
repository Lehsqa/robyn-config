from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from robyn import Request, Response, Robyn


def register(app: Robyn) -> None:
    @app.get(
        "/metrics",
        openapi_name="Metrics",
        openapi_tags=["Metrics"],
    )
    async def metrics(_: Request) -> Response:
        """Returns Prometheus metrics in text exposition format."""
        return Response(
            200,
            {"Content-Type": CONTENT_TYPE_LATEST},
            generate_latest(),
        )
