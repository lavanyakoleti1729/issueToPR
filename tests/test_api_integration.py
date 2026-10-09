from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.main import app, get_db, require_key
from app.database.db import Base


def test_create_read_and_cancel(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    def db_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_key] = lambda: None
    monkeypatch.setattr("app.api.main.init_db", lambda: None)
    monkeypatch.setattr(
        "app.api.main.run_task.delay", lambda task_id: type("Job", (), {"id": "job-1"})()
    )
    monkeypatch.setattr("app.api.main.celery_app.control.revoke", lambda *args, **kwargs: None)
    try:
        with TestClient(app) as client:
            response = client.post(
                "/tasks", json={"repository": "example/repo", "issue_number": 42}
            )
            assert response.status_code == 202
            task_id = response.json()["id"]
            assert client.get(f"/tasks/{task_id}").json()["status"] == "queued"
            assert client.get(f"/tasks/{task_id}/logs").json()["events"] == []
            assert client.get(f"/tasks/{task_id}/diff").text == ""
            assert client.post(f"/tasks/{task_id}/cancel").json()["status"] == "cancelled"
    finally:
        app.dependency_overrides.clear()
