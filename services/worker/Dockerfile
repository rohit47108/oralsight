FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --no-install-project \
    && adduser --disabled-password --gecos "" --uid 10001 oralsight

COPY src ./src

USER oralsight
EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["/app/.venv/bin/python", "-m", "oralsight_worker.main", "health", "--url", "http://127.0.0.1:8010/readyz"]

CMD ["/app/.venv/bin/python", "-m", "uvicorn", "oralsight_worker.main:app", "--host", "0.0.0.0", "--port", "8010", "--no-access-log", "--no-server-header"]
