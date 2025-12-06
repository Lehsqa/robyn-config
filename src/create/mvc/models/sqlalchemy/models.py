from datetime import datetime
from typing import TypeVar

from sqlalchemy import MetaData, SmallInteger, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..authentication import AuthProvider

__all__ = (
    "Base",
    "ConcreteTable",
    "UsersTable",
    "NewsLetterSubscriptionsTable",
)

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
        default=datetime.utcnow, server_default=func.CURRENT_TIMESTAMP()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        server_default=func.CURRENT_TIMESTAMP(),
    )


class BaseTable(TimestampMixin, Base):
    __abstract__ = True


ConcreteTable = TypeVar("ConcreteTable", bound="BaseTable")


class UsersTable(BaseTable):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password: Mapped[str | None] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=False, server_default="0")
    role: Mapped[int] = mapped_column(
        SmallInteger, default=1, server_default="1"
    )
    auth_provider: Mapped[str] = mapped_column(
        default=AuthProvider.INTERNAL,
        server_default=AuthProvider.INTERNAL,
    )


class NewsLetterSubscriptionsTable(BaseTable):
    __tablename__ = "news_letter_subscriptions"

    email: Mapped[str] = mapped_column(unique=True, index=True)
