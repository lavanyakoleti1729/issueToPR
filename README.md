# Issue Agent

An autonomous GitHub issue worker. FastAPI accepts a task, Celery runs a LangGraph workflow, PostgreSQL keeps the history, and a React dashboard follows progress. The worker retrieves an issue, clones its repository, plans a focused patch, runs tests in Docker, repairs failures up to five times, reviews the diff, and opens a pull request when the review approves it.

