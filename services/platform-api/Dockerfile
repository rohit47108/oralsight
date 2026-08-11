# syntax=docker/dockerfile:1.7
FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN addgroup --system oralsight && adduser --system --ingroup oralsight oralsight
COPY --from=builder --chown=oralsight:oralsight /app/.venv /app/.venv
COPY --chown=oralsight:oralsight alembic.ini ./alembic.ini
COPY --chown=oralsight:oralsight alembic ./alembic

USER oralsight
EXPOSE 8080
CMD ["uvicorn", "oralsight_platform.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log", "--no-server-header"]
