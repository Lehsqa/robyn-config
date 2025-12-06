"""Factory helpers for creating configured Robyn applications."""

from collections.abc import Iterable
from typing import Callable

from robyn import Response, Robyn
from robyn.authentication import AuthenticationHandler

RouteRegistrar = Callable[[Robyn], None]
MiddlewareRegistrar = Callable[[Robyn], None]


def create(
    import_name: str,
    *,
    route_registrars: Iterable[RouteRegistrar] | None = None,
    middlewares: Iterable[MiddlewareRegistrar] | None = None,
    exception_handler: Callable[[Exception], Response] | None = None,
    authentication_handler: AuthenticationHandler | None = None,
    **robyn_kwargs,
) -> Robyn:
    """Create a Robyn application with optional route and middleware registrars."""

    app = Robyn(import_name, **robyn_kwargs)

    if exception_handler is not None:
        app.exception(exception_handler)

    if authentication_handler is not None:
        app.configure_authentication(authentication_handler)

    if middlewares is not None:
        for middleware in middlewares:
            middleware(app)

    if route_registrars is not None:
        for register in route_registrars:
            register(app)

    return app
