from huey import RedisHuey

from ...config import settings

huey = RedisHuey(settings.worker.queue, url=settings.worker.redis_url)
