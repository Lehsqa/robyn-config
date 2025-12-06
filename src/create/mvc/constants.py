from enum import IntEnum


class Role(IntEnum):
    USER = 1
    ADMIN = 2

    @classmethod
    def values(cls) -> list[int]:
        return [member.value for member in cls]
