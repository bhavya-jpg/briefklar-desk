"""FastAPI app: API plus the locally built frontend. No outbound traffic except to LLM_BASE_URL."""

from __future__ import annotations

import asyncio
import logging
import mimetypes
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from briefklar.api.routes import router
from briefklar.config import Settings, get_settings
from briefklar.llm.client import LLMClient
from briefklar.session.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("briefklar")

SWEEP_INTERVAL_S = 60
mimetypes.add_type("font/woff2", ".woff2")  # not known to slim base images
# The browser may only talk to this origin: no CDN, no fonts, no analytics can load even by mistake.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'self'; frame-src 'self'; "
    "object-src 'none'; base-uri 'self'; form-action 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "SAMEORIGIN",
}


def create_app(settings: Settings | None = None, client: LLMClient | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def sweep() -> None:
            while True:
                await asyncio.sleep(SWEEP_INTERVAL_S)
                expired = app.state.store.sweep()
                if expired:
                    log.info("wiped %d idle case(s)", len(expired))

        task = asyncio.create_task(sweep())
        log.info("mode=%s model=%s offline=%s", settings.mode, settings.llm_name, settings.offline)
        try:
            yield
        finally:
            task.cancel()
            app.state.store.wipe_all()

    app = FastAPI(title="Briefklar Desk", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.store = Store(settings)
    app.state.client = client or LLMClient(settings)
    app.include_router(router)

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    static = settings.static_dir

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found.")
        candidate = (static / path).resolve()
        if path and candidate.is_file() and static.resolve() in candidate.parents:
            return FileResponse(candidate)
        for fallback in ("200.html", "index.html"):  # single-page app: every route serves the shell
            if (static / fallback).is_file():
                return FileResponse(static / fallback, headers={"Cache-Control": "no-store"})
        raise HTTPException(503, "The frontend is not built. Run `npm run build` in frontend/, or use `make run`.")

    return app


app = create_app()
