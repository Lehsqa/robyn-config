from robyn import Robyn

from .views import authentication, users


def register_routes(app: Robyn) -> None:
    users.register(app)
    authentication.register(app)
