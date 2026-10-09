from app.agents.workflow import Orchestrator
from app.config.settings import get_settings
from app.database.db import SessionLocal
from workers.celery_app import celery_app


@celery_app.task(name="issue_agent.run_task")
def run_task(task_id: str) -> None:
    with SessionLocal() as db:
        Orchestrator(db, get_settings()).run(task_id)
