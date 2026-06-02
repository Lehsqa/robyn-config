from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .tasks import periodic_job

scheduler = BlockingScheduler()
scheduler.add_job(
    periodic_job.send,
    CronTrigger.from_crontab("*/5 * * * *"),
)

if __name__ == "__main__":
    scheduler.start()
