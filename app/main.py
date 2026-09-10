from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import UPLOADS_DIR, Base, engine
from app.routers import buildings, facilities, images, reports, resources, stock

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Facility Log")

app.include_router(facilities.router)
app.include_router(buildings.router)
app.include_router(resources.router)
app.include_router(stock.router)
app.include_router(reports.router)
app.include_router(images.router)

app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
