from pathlib import Path
from types import SimpleNamespace

from app.tools.sandbox import DockerSandbox


def test_docker_command_has_isolation(monkeypatch):
    command_seen = []

    def fake_run(command, **kwargs):
        command_seen.extend(command)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("app.tools.sandbox.subprocess.run", fake_run)
    settings = SimpleNamespace(
        sandbox_cpus=1, sandbox_memory="1g", sandbox_timeout=10, sandbox_image="runner"
    )
    result = DockerSandbox(settings).run_tests(Path("/tmp"), ["pytest", "-q"])
    assert result.exit_code == 0
    assert ["--network", "none"] == command_seen[
        command_seen.index("--network") : command_seen.index("--network") + 2
    ]
    assert "--read-only" in command_seen and "--cap-drop" in command_seen
    assert "--user" in command_seen and "1000:1000" in command_seen
    assert f"type=bind,src={Path('/tmp').resolve()},dst=/source,readonly" in command_seen
