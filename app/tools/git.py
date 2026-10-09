import os
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def git(root: Path, *args: str, timeout: int = 120, env: dict | None = None) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    if proc.returncode:
        raise GitError(proc.stderr[:2000])
    return proc.stdout.strip()


def clone(repository: str, workspace: Path, token: str) -> Path:
    workspace.mkdir(parents=True, exist_ok=False)
    repo = workspace / "repo"
    url = f"https://github.com/{repository}.git"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if token:
        # Git's extra header stays in this process environment; it is never passed to Docker.
        import base64

        value = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env["GIT_CONFIG_COUNT"] = "1"
        env["GIT_CONFIG_KEY_0"] = "http.https://github.com/.extraheader"
        env["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {value}"
    git(workspace, "clone", "--depth", "1", "--", url, str(repo), timeout=180, env=env)
    return repo


def create_branch(repo: Path, branch: str) -> None:
    git(repo, "checkout", "-b", branch)


def commit_and_push(
    repo: Path, branch: str, message: str, token: str, author_name: str, author_email: str
) -> None:
    git(repo, "add", "-A")
    if not git(repo, "status", "--porcelain"):
        raise GitError("No changes to commit")
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    git(repo, "commit", "-m", message[:200], env=env)
    import base64

    value = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {value}",
        }
    )
    git(repo, "push", "origin", branch, timeout=180, env=env)
