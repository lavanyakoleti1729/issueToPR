from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TaskCreate(BaseModel):
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    issue_number: int = Field(gt=0)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("Invalid repository")
        return value


class Plan(BaseModel):
    summary: str
    files: list[str]
    steps: list[str]
    test_command: list[str]


class PatchOutput(BaseModel):
    patch: str = Field(description="Unified git diff patch, including diff --git headers")
    explanation: str


class Review(BaseModel):
    approved: bool
    findings: list[str]
    summary: str


class Issue(BaseModel):
    title: str
    body: str = ""
    html_url: str
    state: str


class ExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timeout: bool = False


class TaskResponse(BaseModel):
    id: str
    repository: str
    issue_number: int
    status: str
    current_agent: str | None
    branch: str | None
    pr_url: str | None
    error: str | None
    repair_attempts: int
    created_at: str
    updated_at: str


class ToolRequest(BaseModel):
    name: Literal["list_files", "read_file", "search_code", "find_symbol", "git_diff"]
    args: dict = Field(default_factory=dict)
