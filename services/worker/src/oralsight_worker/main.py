"""Worker health API and command-line entry point."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import __version__
from .runtime import Runtime
from .settings import Settings

for noisy_logger in ("httpx", "httpcore", "redis"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)

RuntimeFactory = Callable[[Settings], Runtime]


def create_app(
    *,
    settings: Settings | None = None,
    runtime_factory: RuntimeFactory = Runtime.build,
) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        runtime = runtime_factory(resolved_settings)
        application.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.close()

    application = FastAPI(
        title="OralSight Worker",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @application.get("/healthz")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "oralsight-worker",
            "version": __version__,
        }

    @application.get("/readyz")
    async def ready(request: Request):
        runtime: Runtime = request.app.state.runtime
        if not await runtime.ready():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "service": "oralsight-worker",
                },
            )
        return {"status": "ready", "service": "oralsight-worker"}

    return application


app = create_app()


async def _health_check(url: str) -> int:
    try:
        async with httpx.AsyncClient(
            timeout=3, follow_redirects=False, trust_env=False
        ) as client:
            response = await client.get(url)
    except httpx.HTTPError:
        return 1
    return 0 if response.status_code == 200 else 1


def cli() -> None:
    parser = argparse.ArgumentParser(description="Run or check the OralSight worker")
    subparsers = parser.add_subparsers(dest="command")
    health = subparsers.add_parser("health", help="check a running worker")
    health.add_argument("--url", default="http://127.0.0.1:8010/readyz")
    serve = subparsers.add_parser("serve", help="run the worker and health API")
    serve.add_argument("--host", default="0.0.0.0")  # noqa: S104
    serve.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()

    if args.command == "health":
        raise SystemExit(asyncio.run(_health_check(args.url)))

    import uvicorn

    uvicorn.run(
        "oralsight_worker.main:app",
        host=getattr(args, "host", "0.0.0.0"),  # noqa: S104
        port=getattr(args, "port", 8010),
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    cli()
