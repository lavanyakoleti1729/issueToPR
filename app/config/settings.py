from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://agent:agent@localhost:5432/agent"
    redis_url: str = "redis://localhost:6379/0"
    github_token: str = ""
    api_key: str = ""
    otel_exporter_otlp_endpoint: str = ""
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    workspace_root: Path = Path("/tmp/issue-agent-workspaces")
    sandbox_image: str = "issue-agent-runner:latest"
    sandbox_cpus: float = 2
    sandbox_memory: str = "2g"
    sandbox_timeout: int = 300
    max_repair_attempts: int = Field(default=5, ge=0, le=5)
    git_author_name: str = "Issue Agent"
    git_author_email: str = "issue-agent@example.invalid"


@lru_cache
def get_settings() -> Settings:
    return Settings()
