from __future__ import annotations

from tortoise import fields

from .base import BaseTable

__all__ = ("NewsLetterSubscriptionsTable",)


class NewsLetterSubscriptionsTable(BaseTable):
    email = fields.CharField(max_length=255, unique=True, index=True)

    class Meta:
        table = "news_letter_subscriptions"
        ordering = ("id",)
