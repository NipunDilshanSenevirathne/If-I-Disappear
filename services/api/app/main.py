"""If I Disappear — API service (FastAPI on Cloud Run).

uvicorn app.main:app --reload --port 8080
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .ai.router import ledger
from .config import get_settings
from .routes import households, meta, shares, sources, work
from .store import get_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
for noisy in ("google_adk", "google.adk", "google_genai", "httpx"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


# The web app talks to its own origin, Google APIs (Firebase sign-in) and, for
# spoken practice, the Gemini Live websocket. Styles allow inline style attributes
# (React); scripts don't allow anything inline.
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "font-src 'self' data:",
        "media-src 'self' blob:",
        "connect-src 'self' https://*.googleapis.com wss://generativelanguage.googleapis.com https://*.firebaseapp.com",
        "frame-src https://*.firebaseapp.com",
        "worker-src 'self' blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Keep today's free-tier counts across restarts (saved once a minute)."""
    store = get_store()
    with contextlib.suppress(Exception):
        ledger().load(await store.get_meta("quota"))

    async def flush():
        while True:
            await asyncio.sleep(60)
            with contextlib.suppress(Exception):
                await store.put_meta("quota", ledger().dump())

    task = asyncio.create_task(flush())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(Exception):
            await store.put_meta("quota", ledger().dump())


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        lifespan=lifespan,
        title="If I Disappear API",
        version=meta.VERSION,
        description="Before someone leaves home for weeks or months: find what stops, fix it in a short plan, practise the handover.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Dev-User"],
    )

    # Compress text: the web app's scripts and styles, and the JSON the dashboard reads. On a
    # phone on a slow network that is about a third of the bytes. Images, fonts and audio are
    # already compressed and are left alone, and so are answers under 1 KB (the live poll).
    app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
        if path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        elif path.startswith("/assets/"):
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        elif (response.headers.get("content-type") or "").startswith("text/html"):
            response.headers.setdefault("Cache-Control", "no-cache")
            response.headers.setdefault("Content-Security-Policy", CSP)
            response.headers.setdefault("X-Frame-Options", "DENY")
        return response

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    for router in (meta.router, households.router, sources.router, work.router, shares.router):
        app.include_router(router)

    # Optional: serve the built web app from the same service (one Cloud Run URL).
    if s.static_dir and s.static_dir.exists():
        index = s.static_dir / "index.html"
        app.mount("/assets", StaticFiles(directory=s.static_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str):
            if path == "api" or path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Not found."})
            candidate = (s.static_dir / path).resolve()
            if path and candidate.is_file() and s.static_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
