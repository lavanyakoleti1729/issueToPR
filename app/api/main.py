import secrets
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.db import (
    AgentRun,
    Artifact,
    Event,
    SessionLocal,
    Task,
    TestRun,
    ToolCall,
    init_db,
)
from app.models.schemas import TaskCreate, TaskResponse
from app.services.telemetry import tracer
from workers.celery_app import celery_app
from workers.tasks import run_task

TASKS_CREATED = Counter("issue_agent_tasks_created_total", "Tasks accepted by the API")
HTTP_REQUESTS = Counter(
    "issue_agent_http_requests_total", "HTTP requests", ["method", "path", "status"]
)
HTTP_DURATION = Histogram(
    "issue_agent_http_request_seconds", "HTTP request duration", ["method", "path"]
)


def require_key(x_api_key: str = Header(default="")):
    expected = get_settings().api_key
    if not expected:
        raise HTTPException(503, "API_KEY is not configured")
    if not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(401, "Invalid API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Issue Agent", lifespan=lifespan, dependencies=[Depends(require_key)])
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8080"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observe(request, call_next):
    start = time.monotonic()
    with tracer().start_as_current_span(f"http.{request.method}") as span:
        span.set_attribute("http.request.method", request.method)
        response = await call_next(request)
        span.set_attribute("http.response.status_code", response.status_code)
    route = request.scope.get("route")
    label = route.path if route else "unmatched"
    HTTP_REQUESTS.labels(request.method, label, str(response.status_code)).inc()
    HTTP_DURATION.labels(request.method, label).observe(time.monotonic() - start)
    return response


def get_db():
    with SessionLocal() as db:
        yield db


DbDep = Annotated[Session, Depends(get_db)]


def task_or_404(db: Session, task_id: str) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


def as_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        repository=task.repository,
        issue_number=task.issue_number,
        status=task.status,
        current_agent=task.current_agent,
        branch=task.branch,
        pr_url=task.pr_url,
        error=task.error,
        repair_attempts=task.repair_attempts,
        created_at=task.created_at.isoformat(),
        updated_at=task.updated_at.isoformat(),
    )


@app.post("/tasks", response_model=TaskResponse, status_code=202)
def create_task(payload: TaskCreate, db: DbDep):
    task = Task(repository=payload.repository, issue_number=payload.issue_number)
    db.add(task)
    db.commit()
    db.refresh(task)
    try:
        job = run_task.delay(task.id)
        task.celery_id = job.id
        db.commit()
    except Exception as exc:
        task.status = "failed"
        task.error = f"Could not enqueue task: {exc}"
        db.commit()
        raise HTTPException(503, "Worker queue unavailable") from exc
    TASKS_CREATED.inc()
    return as_response(task)


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: DbDep):
    return as_response(task_or_404(db, task_id))


@app.get("/tasks/{task_id}/logs")
def get_logs(task_id: str, db: DbDep):
    task_or_404(db, task_id)
    events = db.scalars(select(Event).where(Event.task_id == task_id).order_by(Event.id)).all()
    tests = db.scalars(select(TestRun).where(TestRun.task_id == task_id).order_by(TestRun.id)).all()
    runs = db.scalars(select(AgentRun).where(AgentRun.task_id == task_id)).all()
    calls = db.scalars(select(ToolCall).where(ToolCall.task_id == task_id)).all()
    return {
        "events": [
            {
                "status": e.status,
                "agent": e.agent,
                "message": e.message,
                "at": e.created_at.isoformat(),
            }
            for e in events
        ],
        "tests": [
            {
                "exit_code": t.exit_code,
                "stdout": t.stdout,
                "stderr": t.stderr,
                "execution_time": t.execution_time,
                "timeout": t.timeout,
            }
            for t in tests
        ],
        "llm_calls": len(runs),
        "tool_calls": len(calls),
        "tokens": sum(r.tokens or 0 for r in runs),
        "cost_usd": sum(r.cost_usd or 0 for r in runs)
        if any(r.cost_usd is not None for r in runs)
        else None,
    }


@app.get("/tasks/{task_id}/diff", response_class=PlainTextResponse)
def get_diff(task_id: str, db: DbDep):
    task_or_404(db, task_id)
    artifact = db.scalar(
        select(Artifact)
        .where(Artifact.task_id == task_id, Artifact.kind == "diff")
        .order_by(Artifact.id.desc())
    )
    return artifact.content if artifact else ""


@app.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
def cancel_task(task_id: str, db: DbDep):
    task = task_or_404(db, task_id)
    if task.status in {"completed", "failed", "cancelled"}:
        return as_response(task)
    task.status = "cancelled"
    db.add(
        Event(
            task_id=task_id,
            status="cancelled",
            agent=task.current_agent,
            message="Cancellation requested",
        )
    )
    db.commit()
    if task.celery_id:
        celery_app.control.revoke(task.celery_id, terminate=False)
    return as_response(task)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
