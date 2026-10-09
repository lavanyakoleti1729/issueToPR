FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ripgrep docker.io \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY workers ./workers
COPY evaluation ./evaluation
RUN pip install --no-cache-dir .
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
