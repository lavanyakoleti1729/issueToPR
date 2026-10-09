import subprocess
import time
from pathlib import Path
from uuid import uuid4

from app.config.settings import Settings
from app.models.schemas import ExecutionResult


class DockerSandbox:
    def __init__(self, settings: Settings):
        self.settings = settings

    def run_tests(self, workspace: Path, command: list[str]) -> ExecutionResult:
        if (
            not command
            or len(command) > 20
            or any(not isinstance(x, str) or len(x) > 300 for x in command)
        ):
            raise ValueError("Invalid test command")
        # No shell: each argument is passed directly. The repository is mounted only in this container.
        container_name = f"issue-agent-{uuid4().hex}"
        cmd = [
            "docker",
            "run",
            "--name",
            container_name,
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--cpus",
            str(self.settings.sandbox_cpus),
            "--memory",
            self.settings.sandbox_memory,
            "--user",
            "1000:1000",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=512m",
            "--mount",
            f"type=bind,src={workspace.resolve()},dst=/source,readonly",
            "--workdir",
            "/tmp",
            self.settings.sandbox_image,
            "sh",
            "-c",
            'mkdir /tmp/work && cp -a /source/. /tmp/work && cd /tmp/work && exec "$@"',
            "sh",
            *command,
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.settings.sandbox_timeout,
                check=False,
            )
            return ExecutionResult(
                exit_code=proc.returncode,
                stdout=proc.stdout[-30_000:],
                stderr=proc.stderr[-30_000:],
                execution_time=time.monotonic() - start,
            )
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                ["docker", "rm", "-f", container_name], capture_output=True, timeout=15, check=False
            )
            return ExecutionResult(
                exit_code=124,
                stdout=(exc.stdout or b"").decode(errors="replace")[-30_000:]
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")[-30_000:],
                stderr=(exc.stderr or b"").decode(errors="replace")[-30_000:]
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")[-30_000:],
                execution_time=time.monotonic() - start,
                timeout=True,
            )
