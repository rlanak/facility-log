from app import envfile  # noqa: F401  (must run before app.auth reads the environment)

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import PlainTextResponse
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app import auth
from app.database import UPLOADS_DIR, Base, apply_migrations, engine
from app.paths import APP_DIR
from app.routers import auth as auth_routes
from app.routers import buildings, facilities, foxhole, images, reports, resources, save, settings, stock
from app.services import discord_dashboard

Base.metadata.create_all(bind=engine)
apply_migrations()


class NoCacheStaticFiles(StaticFiles):
    """This is a locally-run app that gets updated via `git pull`, so the browser
    must always re-check with the server instead of serving a stale cached copy
    of app.js/index.html from a previous version."""

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store"
        return response


class ImageOnlyStaticFiles(StaticFiles):
    """/uploads serves screenshots only: any other extension is a 404, so a
    file that isn't an image can never be served from the app's own origin
    (see routers/images.py)."""

    async def get_response(self, path: str, scope: Scope):
        if not path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            return PlainTextResponse("Not Found", status_code=404)
        return await super().get_response(path, scope)


# Defense in depth against injected HTML: scripts only from this site and the
# pinned Tailwind CDN (no inline scripts), styles also from Google Fonts,
# images from this site and Discord avatars, fetches to this site and to the
# user's own Ollama on their PC ("IA do meu computador", any localhost port).
CSP = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdn.tailwindcss.com",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: blob: https://cdn.discordapp.com",
        "connect-src 'self' http://localhost:* http://127.0.0.1:*",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Discord webhook dashboards (opt-in per facility; idle when none is set).
    task = asyncio.create_task(discord_dashboard.run_forever())
    yield
    task.cancel()


app = FastAPI(title="Facility Log", lifespan=lifespan)

# Minimum security (03/11/2026): the app must never end up open to the
# internet without login by accident.
# - FACILITY_LOG_REQUIRE_LOGIN=1 (set in the Dockerfile): refuse to start
#   without the Discord login configured — a server deploy with a missing
#   .env would otherwise serve everything to anyone.
# - Local mode (no login) only answers this same PC: a request through a
#   tunnel/proxy (cloudflared, Caddy) or from another machine gets 403.
#   FACILITY_LOG_ALLOW_OPEN=1 lifts this (trusted LAN), on purpose only.
if not auth.config.enabled and os.environ.get("FACILITY_LOG_REQUIRE_LOGIN") == "1":
    raise RuntimeError("FACILITY_LOG_REQUIRE_LOGIN=1 but the Discord login isn't configured (see .env.example)")


@app.middleware("http")
async def security_headers(request, call_next):
    if not auth.config.enabled and os.environ.get("FACILITY_LOG_ALLOW_OPEN") != "1" and not auth.is_local_request(request):
        return PlainTextResponse(
            "facility-log em modo local só responde neste PC. Pra acessar de fora, ligue o login pelo Discord (.env).",
            status_code=403,
        )
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", CSP)
    return response


# Web mode (Discord login) only when configured — see app/auth.py. Local
# mode stays exactly as it was: no login, no session cookie.
if auth.config.enabled:
    missing = auth.config.missing()
    if missing:
        raise RuntimeError(f"Discord login is on (DISCORD_CLIENT_ID set) but missing: {', '.join(missing)}")
    app.middleware("http")(auth.gate)
    # Added after the gate so it wraps it (outermost) — the gate reads the session.
    app.add_middleware(
        SessionMiddleware,
        secret_key=auth.config.session_secret,
        session_cookie="facility_log_session",
        max_age=auth.SESSION_SECONDS,
        same_site="lax",
        https_only=auth.config.redirect_uri.startswith("https://"),
    )

app.include_router(auth_routes.router)

app.include_router(facilities.router)
app.include_router(buildings.router)
app.include_router(resources.router)
app.include_router(stock.router)
app.include_router(reports.router)
app.include_router(images.router)
app.include_router(foxhole.router)
app.include_router(save.router)
app.include_router(settings.router)

app.mount("/uploads", ImageOnlyStaticFiles(directory=UPLOADS_DIR), name="uploads")

WEB_DIR = APP_DIR / "web"
app.mount("/", NoCacheStaticFiles(directory=WEB_DIR, html=True), name="web")
