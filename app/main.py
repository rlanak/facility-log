from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.database import UPLOADS_DIR, Base, apply_migrations, engine
from app.paths import BUNDLE_DIR
from app.routers import buildings, facilities, foxhole, images, reports, resources, stock, tunnels

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

app.include_router(facilities.router)
app.include_router(buildings.router)
app.include_router(resources.router)
app.include_router(stock.router)
app.include_router(reports.router)
app.include_router(images.router)
app.include_router(foxhole.router)
app.include_router(tunnels.router)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

WEB_DIR = BUNDLE_DIR / "web"
app.mount("/", NoCacheStaticFiles(directory=WEB_DIR, html=True), name="web")
