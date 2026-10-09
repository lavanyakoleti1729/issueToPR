import os
import shutil
import tempfile
from pathlib import Path

import pytest

from app.config.settings import Settings
from app.tools.sandbox import DockerSandbox


@pytest.mark.skipif(
    os.getenv("RUN_DOCKER_TESTS") != "1" or not shutil.which("docker"),
    reason="Docker integration test is opt-in",
)
def test_real_container_runs_generated_test():
    settings = Settings()
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=settings.workspace_root) as directory:
        (Path(directory) / "test_sample.py").write_text("def test_ok():\n    assert 2 + 2 == 4\n")
        result = DockerSandbox(settings).run_tests(Path(directory), ["pytest", "-q"])
        assert result.exit_code == 0, result.stderr
        assert "1 passed" in result.stdout
