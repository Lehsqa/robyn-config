from typing import TypeVar

from tortoise import fields
from tortoise.models import Model

from ..authentication import AuthProvider

__all__ = (
    "BaseTable",
    "ConcreteTable",
    "UsersTable",
    "NewsLetterSubscriptionsTable",
)


class BaseTable(Model):
    id = fields.IntField(pk=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        abstract = True


ConcreteTable = TypeVar("ConcreteTable", bound="BaseTable")


class UsersTable(BaseTable):
    username = fields.CharField(max_length=255, unique=True, index=True)
    email = fields.CharField(max_length=255, unique=True, index=True)
    password = fields.CharField(max_length=512, null=True)
    is_active = fields.BooleanField(default=False)
    role = fields.SmallIntField(default=1)
    auth_provider = fields.CharEnumField(
        enum_type=AuthProvider, default=AuthProvider.INTERNAL
    )

    class Meta:
        table = "users"
        ordering = ("id",)


class NewsLetterSubscriptionsTable(BaseTable):
    email = fields.CharField(max_length=255, unique=True, index=True)

    class Meta:
        table = "news_letter_subscriptions"
        ordering = ("id",)
