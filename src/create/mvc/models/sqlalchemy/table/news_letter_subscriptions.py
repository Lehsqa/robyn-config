from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseTable

__all__ = ("NewsLetterSubscriptionsTable",)


class NewsLetterSubscriptionsTable(BaseTable):
    __tablename__ = "news_letter_subscriptions"

    email: Mapped[str] = mapped_column(unique=True, index=True)
