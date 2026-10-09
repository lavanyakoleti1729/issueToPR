from types import SimpleNamespace

from app.agents.workflow import Orchestrator


def test_repair_limit_routes():
    orchestrator = object.__new__(Orchestrator)
    orchestrator.settings = SimpleNamespace(max_repair_attempts=5)
    orchestrator.event = lambda *args: None
    assert (
        orchestrator.after_test({"test_result": {"exit_code": 0}, "repair_attempts": 5}) == "review"
    )
    assert (
        orchestrator.after_test({"test_result": {"exit_code": 1}, "repair_attempts": 4}) == "repair"
    )
    assert (
        orchestrator.after_test({"test_result": {"exit_code": 1}, "repair_attempts": 5}) == "failed"
    )
    assert (
        orchestrator.after_review({"review": {"approved": True}, "repair_attempts": 5}) == "publish"
    )
    assert (
        orchestrator.after_review({"review": {"approved": False}, "repair_attempts": 5}) == "failed"
    )
