from __future__ import annotations

from typing import TypeVar

from tortoise import fields
from tortoise.models import Model

__all__ = ("BaseTable", "ConcreteTable")


class BaseTable(Model):
    id = fields.IntField(pk=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        abstract = True


ConcreteTable = TypeVar("ConcreteTable", bound="BaseTable")
