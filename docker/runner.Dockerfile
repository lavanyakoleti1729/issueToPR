FROM python:3.12-slim
RUN groupadd -g 1000 runner && useradd -u 1000 -g 1000 -m runner \
    && pip install --no-cache-dir pytest
USER runner
WORKDIR /workspace

