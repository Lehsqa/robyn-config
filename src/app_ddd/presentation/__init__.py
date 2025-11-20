from robyn import Robyn

from . import authentication, healthcheck, users


def register_routes(app: Robyn) -> None:
    healthcheck.register(app)
    users.register(app)
    authentication.register(app)
