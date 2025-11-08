"""Input validators reused by presentation layers."""

from ...infrastructure.application import UnprocessableError


def password_nist(payload: str) -> str:
    """Check if the password suits the NIST requirements."""

    if len(payload) < 8:
        raise UnprocessableError(
            message="The password must be at least 8 characters long."
        )

    if len(payload) > 64:
        raise UnprocessableError(
            message="The password must be at most 64 characters long."
        )

    if not any(char.isdigit() for char in payload):
        raise UnprocessableError(
            message="The password must contain at least one digit."
        )

    if not any(char.isupper() for char in payload):
        raise UnprocessableError(
            message="The password must contain at least one uppercase letter."
        )

    if not any(char.islower() for char in payload):
        raise UnprocessableError(
            message="The password must contain at least one lowercase letter."
        )

    if not any(char in "!@#$%^&*()-+?_=,<>/;:[]{}" for char in payload):
        raise UnprocessableError(
            message="The password must contain at least one special character."
        )

    return payload
