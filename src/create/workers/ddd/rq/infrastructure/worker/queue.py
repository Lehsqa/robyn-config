from redis import Redis
from rq import Queue

from ...config import settings

connection = Redis.from_url(settings.worker.redis_url)
queue = Queue(settings.worker.queue, connection=connection)
