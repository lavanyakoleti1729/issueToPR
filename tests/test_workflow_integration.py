import shutil
import subprocess

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agents.workflow import Orchestrator
from app.config.settings import Settings
from app.database.db import Base, Event, Task
from app.database.db import TestRun as StoredTestRun
from app.models.schemas import ExecutionResult, Issue, PatchOutput, Plan, Review


def test_failure_repair_review_and_pr(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "sample.py").write_text("def value():\n    return 1\n")
    subprocess.run(["git", "add", "sample.py"], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "initial",
        ],
        cwd=source,
        check=True,
    )

    def fake_clone(repository, workspace, token):
        workspace.mkdir(parents=True)
        destination = workspace / "repo"
        shutil.copytree(source, destination)
        return destination

    monkeypatch.setattr("app.agents.workflow.clone", fake_clone)
    monkeypatch.setattr("app.agents.workflow.commit_and_push", lambda *args: None)

    class GitHub:
        def issue(self, repository, number):
            return Issue(
                title="Return two",
                body="Make value return two",
                html_url="https://github.com/example/repo/issues/42",
                state="open",
            )

        def repository(self, repository):
            return {"default_branch": "main"}

        def create_pr(self, *args):
            return "https://github.com/example/repo/pull/1"

    patch1 = "diff --git a/sample.py b/sample.py\n--- a/sample.py\n+++ b/sample.py\n@@ -1,2 +1,2 @@\n def value():\n-    return 1\n+    return 3\n"
    patch2 = "diff --git a/sample.py b/sample.py\n--- a/sample.py\n+++ b/sample.py\n@@ -1,2 +1,2 @@\n def value():\n-    return 3\n+    return 2\n"

    class LLM:
        def __init__(self):
            self.last_usage = {"total_tokens": 10}
            self.patches = iter([patch1, patch2])

        def structured(self, system, user, schema):
            if schema is Plan:
                return Plan(
                    summary="Change value",
                    files=["sample.py"],
                    steps=["edit"],
                    test_command=["pytest", "-q"],
                )
            if schema is PatchOutput:
                return PatchOutput(patch=next(self.patches), explanation="Fix value")
            if schema is Review:
                return Review(approved=True, findings=[], summary="Value now returns two")
            raise AssertionError(schema)

    class Sandbox:
        calls = 0

        def run_tests(self, workspace, command):
            self.calls += 1
            return ExecutionResult(
                exit_code=1 if self.calls == 1 else 0,
                stdout="failed" if self.calls == 1 else "passed",
                stderr="",
                execution_time=0.1,
            )

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        task = Task(repository="example/repo", issue_number=42)
        db.add(task)
        db.commit()
        settings = Settings(workspace_root=tmp_path / "workspaces", max_repair_attempts=5)
        Orchestrator(db, settings, github=GitHub(), llm=LLM(), sandbox=Sandbox()).run(task.id)
        db.refresh(task)
        assert task.status == "completed"
        assert task.repair_attempts == 1
        assert task.pr_url == "https://github.com/example/repo/pull/1"
        assert (
            len(db.scalars(select(StoredTestRun).where(StoredTestRun.task_id == task.id)).all())
            == 2
        )
        assert any(
            event.agent == "repair"
            for event in db.scalars(select(Event).where(Event.task_id == task.id))
        )
        assert not (settings.workspace_root / task.id).exists()
