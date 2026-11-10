"""Screenshots are only needed while they're being read — find the items,
read the numbers, learn exemplars. Nothing shows them again afterwards, and
kept forever they only grow the data folder (and every daily backup of it).
So, when asked to, the ones older than keep_days() are deleted: the file,
its upload_images row, and the pointer stock entries kept to it (the entries
themselves stay).

Off unless FACILITY_LOG_UPLOAD_DAYS says how many days to keep them (e.g.
30): deleting someone's files is never the app's own idea. When on, it runs
when the app starts and then once a day (app/main.py lifespan).
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app import models
from app.database import UPLOADS_DIR, SessionLocal, upload_path

log = logging.getLogger("facility_log.uploads")

DEFAULT_DAYS = 0  # 0 = keep forever
INTERVAL_SECONDS = 24 * 3600


def keep_days() -> int:
    try:
        return max(0, int(os.environ.get("FACILITY_LOG_UPLOAD_DAYS", DEFAULT_DAYS)))
    except ValueError:
        return DEFAULT_DAYS


def purge(now: datetime | None = None) -> int:
    """Deletes the screenshots older than keep_days(); returns how many files
    went. Also files in the uploads folder no row points to any more (their
    building was deleted) — same age, by the file's own date."""
    days = keep_days()
    if not days:
        return 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    removed = 0
    db = SessionLocal()
    try:
        for image in db.query(models.UploadImage).filter(models.UploadImage.uploaded_at < cutoff).all():
            try:
                upload_path(image.file_path).unlink(missing_ok=True)
            except OSError as exc:
                log.warning("não apagou %s: %s", image.file_path, exc)
                continue
            db.execute(
                update(models.StockEntry).where(models.StockEntry.source_image_id == image.id).values(source_image_id=None)
            )
            db.delete(image)
            removed += 1
        db.commit()
        known = {upload_path(row.file_path).name for row in db.query(models.UploadImage)}
    finally:
        db.close()
    for path in UPLOADS_DIR.iterdir():
        try:
            if path.is_file() and path.name not in known and path.stat().st_mtime < cutoff.timestamp():
                path.unlink()
                removed += 1
        except OSError as exc:
            log.warning("não apagou %s: %s", path, exc)
    return removed


async def run_forever() -> None:
    while True:
        try:
            removed = await asyncio.to_thread(purge)
            if removed:
                log.info("%s print(s) com mais de %s dias apagado(s)", removed, keep_days())
        except Exception:
            log.exception("limpeza de prints")
        await asyncio.sleep(INTERVAL_SECONDS)
