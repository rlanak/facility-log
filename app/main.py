from app import envfile  # noqa: F401  (must run before app.auth reads the environment)

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app import auth
from app.database import UPLOADS_DIR, Base, apply_migrations, engine
from app.paths import BUNDLE_DIR
from app.routers import auth as auth_routes
from app.routers import buildings, facilities, foxhole, images, reports, resources, save, settings, stock

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


app = FastAPI(title="Facility Log")

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
        max_age=30 * 24 * 3600,
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

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

WEB_DIR = BUNDLE_DIR / "web"
app.mount("/", NoCacheStaticFiles(directory=WEB_DIR, html=True), name="web")
