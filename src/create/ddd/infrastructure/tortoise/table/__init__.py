from .authentication import UsersTable
from .base import BaseTable, ConcreteTable
from .news_letter_subscriptions import NewsLetterSubscriptionsTable

__all__ = (
    "BaseTable",
    "ConcreteTable",
    "UsersTable",
    "NewsLetterSubscriptionsTable",
)
