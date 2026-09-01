FROM python:3.12-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    STOMA3D_RELEASE_MANIFEST_PATH=/app/release/release-manifest.json

WORKDIR /app

COPY requirements.lock.txt ./

RUN python -m pip install --require-hashes --no-deps -r requirements.lock.txt \
    && adduser --disabled-password --gecos "" --uid 10001 stoma3d

COPY src ./src
COPY release ./release

USER stoma3d
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).read()"

# Access logging is disabled because multipart requests can contain sensitive
# captures.  Application logs include only method, path, status, and request ID.
CMD ["python", "-m", "uvicorn", "stoma3d_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-server-header"]
