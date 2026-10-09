import subprocess

import pytest

from app.tools.repository import RepositoryTools


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "sample.py").write_text("def value():\n    return 1\n")
    subprocess.run(["git", "add", "sample.py"], cwd=tmp_path, check=True)
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
        cwd=tmp_path,
        check=True,
    )
    return RepositoryTools(tmp_path)


def test_read_search_and_patch(repo):
    assert repo.list_files() == ["sample.py"]
    assert "def value" in repo.find_symbol("value")
    patch = "diff --git a/sample.py b/sample.py\n--- a/sample.py\n+++ b/sample.py\n@@ -1,2 +1,2 @@\n def value():\n-    return 1\n+    return 2\n"
    repo.apply_patch(patch)
    assert "return 2" in repo.read_file("sample.py")
    assert "+    return 2" in repo.git_diff()


def test_path_escape_and_symlink_blocked(repo, tmp_path):
    (tmp_path / "link").symlink_to("/etc/passwd")
    for path in ["../outside", ".git/config", "link", "/etc/passwd", ".github/workflows/ci.yml"]:
        with pytest.raises(ValueError):
            repo.read_file(path)
