import os
import re
import subprocess
from pathlib import Path

SKIP = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
MAX_READ = 40_000


class RepositoryTools:
    def __init__(self, root: Path):
        self.root = root.resolve(strict=True)

    def _file(self, name: str) -> Path:
        if (
            name.startswith(("/", "\\"))
            or "\\" in name
            or any(part in {"..", ".git"} for part in Path(name).parts)
        ):
            raise ValueError("Forbidden repository path")
        if name.startswith(".github/workflows/"):
            raise ValueError("Workflow files are not agent editable")
        path = self.root / name
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(self.root):
            raise ValueError("Path escapes repository")
        if path.is_symlink():
            raise ValueError("Symlinks are not accepted")
        return path

    def list_files(self, limit: int = 300) -> list[str]:
        files = []
        for current, directories, names in os.walk(self.root, followlinks=False):
            directories[:] = [
                name
                for name in directories
                if name not in SKIP and not (Path(current) / name).is_symlink()
            ]
            for name in names:
                path = Path(current) / name
                if path.is_file() and not path.is_symlink():
                    files.append(str(path.relative_to(self.root)))
                    if len(files) >= min(limit, 1000):
                        return sorted(files)
        return sorted(files)

    def read_file(self, name: str, start_line: int = 1, max_lines: int = 200) -> str:
        path = self._file(name)
        if not path.is_file() or path.stat().st_size > MAX_READ * 5:
            raise ValueError("File missing or too large")
        lines = path.read_text(errors="replace").splitlines()
        return "\n".join(
            f"{i + 1}: {line}"
            for i, line in enumerate(lines)
            if start_line <= i + 1 < start_line + min(max_lines, 400)
        )[:MAX_READ]

    def search_code(self, query: str, limit: int = 80) -> str:
        if not query or len(query) > 200:
            raise ValueError("Invalid query")
        proc = subprocess.run(
            ["rg", "-n", "-F", "--max-count", "3", "--", query, "."],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if proc.returncode not in (0, 1):
            raise RuntimeError(proc.stderr[:1000])
        return "\n".join(proc.stdout.splitlines()[: min(limit, 200)])[:MAX_READ]

    def find_symbol(self, symbol: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", symbol):
            raise ValueError("Invalid symbol")
        return self.search_code(symbol)

    def apply_patch(self, patch: str) -> None:
        if not patch or len(patch) > 200_000:
            raise ValueError("Empty or excessive patch")
        if (
            "GIT binary patch" in patch
            or "new file mode 120000" in patch
            or "new file mode 160000" in patch
        ):
            raise ValueError("Binary, symlink and submodule patches are not supported")
        for line in patch.splitlines():
            if line.startswith("diff --git "):
                parts = line.split()[2:]
            elif line.startswith(("--- ", "+++ ")):
                parts = line.split()[1:]
            else:
                parts = []
            for part in parts:
                if part == "/dev/null":
                    continue
                name = part[2:] if part.startswith(("a/", "b/")) else part
                self._file(name)
        check = subprocess.run(
            ["git", "apply", "--check", "--whitespace=error", "-"],
            cwd=self.root,
            input=patch,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if check.returncode:
            raise ValueError(check.stderr[:2000])
        proc = subprocess.run(
            ["git", "apply", "--whitespace=error", "-"],
            cwd=self.root,
            input=patch,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if proc.returncode:
            raise ValueError(proc.stderr[:2000])
        subprocess.run(
            ["git", "add", "-N", "--", "."],
            cwd=self.root,
            check=True,
            capture_output=True,
            timeout=15,
        )

    def git_diff(self) -> str:
        proc = subprocess.run(
            ["git", "diff", "--", "."],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr[:1000])
        if len(proc.stdout) > 60_000:
            raise ValueError("Diff exceeds the review context limit")
        return proc.stdout

    def changed_files(self) -> list[str]:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=self.root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if proc.returncode:
            raise RuntimeError(proc.stderr[:1000])
        return [line[3:] for line in proc.stdout.splitlines()]
