import dramatiq

from ...config import settings
from .broker import broker


@dramatiq.actor(broker=broker, queue_name=settings.worker.queue)
def example_task(value: str) -> str:
    return value


@dramatiq.actor(broker=broker, queue_name=settings.worker.queue)
def periodic_job() -> None:
    return None
