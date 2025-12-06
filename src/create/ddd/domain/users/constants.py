from enum import IntEnum


class Role(IntEnum):
    USER = 1
    ADMIN = 2

    @classmethod
    def values(cls) -> tuple[int, ...]:
        return tuple(member.value for member in cls)
