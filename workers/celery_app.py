from celery import Celery

from app.config.settings import get_settings

settings = get_settings()
celery_app = Celery(
    "issue_agent", broker=settings.redis_url, backend=settings.redis_url, include=["workers.tasks"]
)
celery_app.conf.update(task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1)
