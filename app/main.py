"""FastAPI app: admin API + channel webhooks."""

import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logging_setup import setup_logging
from app.routers import (
    auth,
    broadcasts,
    cases,
    contacts,
    conversations,
    dashboard,
    inbox_tools,
    misc,
    simulator,
    webhooks,
)
from app.routers import (
    settings as settings_router,
)

log = logging.getLogger("onti.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from app.seed import ensure_admin

    try:
        await ensure_admin()
    except Exception:
        log.exception("could not seed the admin user (did migrations run?)")
    log.info("API ready (provider=%s, whatsapp=%s)", settings.llm_provider,
             "configured" if settings.whatsapp_configured else "not configured")  # fmt: skip
    yield


app = FastAPI(title="Onti Erlina Hub", version="0.1.0", lifespan=lifespan)

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@app.middleware("http")
async def origin_check(request: Request, call_next):
    """CSRF defence for cookie-authenticated calls: a state-changing request that
    carries an Origin header must come from the admin UI (or the API itself).
    Webhooks are signed instead and come without a browser Origin."""
    origin = request.headers.get("origin")
    if request.method in UNSAFE and origin and not request.url.path.startswith("/webhook/"):
        allowed = set(settings.allowed_origins)
        own = f"{request.url.scheme}://{request.url.netloc}"
        parsed = urlparse(origin)
        if origin not in allowed and origin != own and parsed.netloc != request.url.netloc:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

for r in (
    misc,
    auth,
    conversations,
    inbox_tools,
    simulator,
    cases,
    contacts,
    broadcasts,
    dashboard,
    settings_router,
    webhooks,
):
    app.include_router(r.router)
