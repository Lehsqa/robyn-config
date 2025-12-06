from enum import StrEnum, auto

from passlib.context import CryptContext


class AuthProvider(StrEnum):
    INTERNAL = auto()
    GOOGLE = auto()
    MICROSOFT = auto()
    META = auto()


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
