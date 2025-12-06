from robyn import Robyn

from .views import authentication, healthcheck, users


def register_routes(app: Robyn) -> None:
    users.register(app)
    authentication.register(app)
    healthcheck.register(app)
