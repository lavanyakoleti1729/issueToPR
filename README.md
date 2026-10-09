# Issue Agent

An autonomous GitHub issue worker. FastAPI accepts a task, Celery runs a LangGraph workflow, PostgreSQL keeps the history, and a React dashboard follows progress. The worker retrieves an issue, clones its repository, plans a focused patch, runs tests in Docker, repairs failures up to five times, reviews the diff, and opens a pull request when the review approves it.

## Setup

Requires Python 3.12+, Docker with the Compose plugin, and a GitHub token with read access to issues and contents plus write access to contents and pull requests on the target repository. The token must be allowed to push the new branch. The default runner image supports Python 3.12 and pytest. Build another runner image with the project's dependencies before processing other languages or projects with additional dependencies.

```sh
cp .env.example .env
# Set GITHUB_TOKEN, LLM_API_KEY, LLM_MODEL, API_KEY and paths in .env.
# WORKSPACE_ROOT must be an absolute host path shared with the Docker daemon.
mkdir -p workspaces
docker build -f docker/runner.Dockerfile -t issue-agent-runner:latest .
docker compose up --build
```

The example paths target this workspace's Colima setup. On Docker Desktop, set `DOCKER_SOCKET=/var/run/docker.sock`; on another machine, set both paths for that machine. The worker mounts the Docker socket, so run it only on a trusted host. Repository code is never given the socket or host credentials. Its tests run in a separate non-root container with no network, a read-only root filesystem, a read-only repository mount, bounded CPU, memory and process counts, and a timeout.

Open `http://localhost:8080`, enter the API key, repository (`owner/name`), and issue number. The API is also available at `http://localhost:8000`:

```sh
curl -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"repository":"your-org/your-repo","issue_number":42}' \
  http://localhost:8000/tasks
```

Use `GET /tasks/{id}`, `GET /tasks/{id}/logs`, `GET /tasks/{id}/diff`, and `POST /tasks/{id}/cancel` with the same header. `GET /metrics` exposes Prometheus metrics and also requires the API key. Cancellation is cooperative at workflow boundaries; an active test container runs until it exits or reaches its timeout.

## Workflow and data

`repository → planner → coder → Docker test → (repair → Docker test, up to five times) → reviewer → commit/push → pull request`

The repository agent lists files and retrieves a small amount of project context and issue-related search results. The planner produces a Pydantic plan. The coding and repair nodes emit unified patches; the tool validates paths and applies them with `git apply`. Review covers correctness, security, performance, maintainability, and coverage. An unapproved review goes through repair and another test. No full repository is sent to the model.

`tasks`, `agent_runs`, `tool_calls`, `test_runs`, `artifacts`, and `events` are SQLAlchemy tables. The API creates tables on startup. For production upgrades, add a migration system before changing the schema. Agent calls record token totals and cost when the provider returns them. OpenTelemetry spans are exported when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; `/metrics` exposes Prometheus request metrics.

The LLM uses an OpenAI-compatible `/chat/completions` endpoint configured by `LLM_API_BASE`, `LLM_API_KEY`, and `LLM_MODEL`. The endpoint must support JSON object responses. A provider may report token counts without cost; missing cost stays unknown.

## Tests and evaluation

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
npm --prefix frontend ci
npm --prefix frontend run build
RUN_DOCKER_TESTS=1 .venv/bin/pytest -q tests/test_docker_integration.py
```

The Docker integration test needs a built runner image and `WORKSPACE_ROOT` on a path shared with the Docker daemon. The benchmark manifest in `evaluation/cases.json` points to real GitHub issues. Use repositories you can push to, or change the cases to writable test repositories containing equivalent issues. Running the benchmark creates branches and pull requests:

```sh
.venv/bin/python -m evaluation.benchmark --api http://localhost:8000 --api-key "$API_KEY"
```

It writes `benchmark-results.json` with success rate, final test pass rate, repair attempts, elapsed time, LLM calls, tool calls, token totals, and provider cost when available. No benchmark results are included because no authenticated end-to-end run has been performed.

## Limits

- The default runner includes pytest but cannot install project dependencies at execution time because network access is disabled. Prepare a trusted runner image with those dependencies and set `SANDBOX_IMAGE` before running such tasks.
- Docker socket access makes the worker a trusted service. Keep the API key and worker network private; the sandbox is the trust boundary for repository code.
- The agent applies text patches and blocks symlinks, binary patches, submodules, `.git`, and GitHub workflow edits. It does not run arbitrary repository setup scripts on the host.
- Automated review is model-based and can miss defects. Inspect a generated pull request before merging it.
- The current worker handles one task at a time in Compose. A task does not resume a partial workflow after an abrupt worker restart.
