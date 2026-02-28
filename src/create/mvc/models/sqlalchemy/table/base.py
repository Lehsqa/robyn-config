from __future__ import annotations

from datetime import datetime
from typing import TypeVar

from sqlalchemy import MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ("Base", "BaseTable", "ConcreteTable")

meta = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = meta


class TimestampMixin:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        server_default=func.CURRENT_TIMESTAMP(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.CURRENT_TIMESTAMP(),
    )


class BaseTable(TimestampMixin, Base):
    __abstract__ = True


ConcreteTable = TypeVar("ConcreteTable", bound="BaseTable")
