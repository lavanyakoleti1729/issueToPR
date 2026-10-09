"""Submit real GitHub issues and report measured outcomes; never invent a score."""

import argparse
import json
import statistics
import time
from pathlib import Path

import httpx


def benchmark(
    api: str, api_key: str, cases: list[dict], poll_seconds: int = 5, max_wait: int = 3600
) -> dict:
    results = []
    with httpx.Client(
        base_url=api.rstrip("/"), timeout=30, headers={"X-API-Key": api_key}
    ) as client:
        for case in cases:
            started = time.monotonic()
            response = client.post(
                "/tasks",
                json={"repository": case["repository"], "issue_number": case["issue_number"]},
            )
            response.raise_for_status()
            task_id = response.json()["id"]
            while True:
                task_response = client.get(f"/tasks/{task_id}")
                task_response.raise_for_status()
                task = task_response.json()
                if task["status"] in {"completed", "failed", "cancelled"}:
                    break
                if time.monotonic() - started > max_wait:
                    client.post(f"/tasks/{task_id}/cancel").raise_for_status()
                    task["status"] = "timeout"
                    break
                time.sleep(poll_seconds)
            logs = client.get(f"/tasks/{task_id}/logs").json()
            tests = logs["tests"]
            results.append(
                {
                    "case": case,
                    "task_id": task_id,
                    "status": task["status"],
                    "success": bool(task.get("pr_url")),
                    "test_pass": bool(tests and tests[-1]["exit_code"] == 0),
                    "repair_attempts": task["repair_attempts"],
                    "execution_seconds": time.monotonic() - started,
                    "test_runs": len(tests),
                    "llm_calls": logs["llm_calls"],
                    "tool_calls": logs["tool_calls"],
                    "tokens": logs["tokens"],
                    "cost_usd": logs["cost_usd"],
                }
            )
    n = len(results)
    return {
        "cases": results,
        "task_success_rate": sum(r["success"] for r in results) / n if n else None,
        "test_pass_rate": sum(r["test_pass"] for r in results) / n if n else None,
        "average_repair_attempts": statistics.mean(r["repair_attempts"] for r in results)
        if n
        else None,
        "average_execution_seconds": statistics.mean(r["execution_seconds"] for r in results)
        if n
        else None,
        "average_llm_calls": statistics.mean(r["llm_calls"] for r in results) if n else None,
        "average_tool_calls": statistics.mean(r["tool_calls"] for r in results) if n else None,
        "total_tokens": sum(r["tokens"] for r in results),
        "total_cost_usd": sum(r["cost_usd"] for r in results)
        if all(r["cost_usd"] is not None for r in results)
        else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--output", type=Path, default=Path("benchmark-results.json"))
    args = parser.parse_args()
    report = benchmark(args.api, args.api_key, json.loads(args.cases.read_text()))
    args.output.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
