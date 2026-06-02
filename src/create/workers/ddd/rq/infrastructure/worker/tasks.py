from datetime import timedelta

from rq import Repeat

from .queue import queue


def example_task(value: str) -> str:
    return value


def periodic_job() -> None:
    return None


def enqueue_delayed_example(value: str):
    return queue.enqueue_in(timedelta(minutes=5), example_task, value)


def enqueue_repeating_example():
    return queue.enqueue(
        periodic_job,
        repeat=Repeat(times=3, interval=300),
    )
