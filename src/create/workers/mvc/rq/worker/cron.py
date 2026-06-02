from rq.cron import register

from ..config import settings
from .tasks import periodic_job

register(periodic_job, queue_name=settings.worker.queue, interval=300)
