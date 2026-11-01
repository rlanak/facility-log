"""Seeds data/icon_exemplars/ from screenshots already confirmed in the past,
so the detector can tell near-identical icons (Assembly Materials tiers) apart
right away instead of only after new confirmations.

How a slot gets its label: the screenshot is re-detected and each slot's
quantity is read; when that quantity matches exactly one value the user
confirmed from that same screenshot (stock_entries with source='ocr'), the
slot is labeled with the confirmed item — not the detector's guess, which
for tiered items may be wrong. Ambiguous matches are skipped.

    .venv/Scripts/python.exe scripts/seed_icon_exemplars.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402
from app.database import UPLOADS_DIR, SessionLocal  # noqa: E402
from app.services import icon_match_service, number_parser  # noqa: E402
from app.services.capture import readers  # noqa: E402


def _value(text: str) -> float | None:
    try:
        return number_parser.parse_quantity(text or "")
    except ValueError:
        return None


def main() -> None:
    reader = readers.read_rapidocr if readers.rapidocr_available() else None
    added = 0
    with SessionLocal() as db:
        confirmed: dict[int, dict[str, float]] = {}
        rows = db.execute(
            select(models.StockEntry.source_image_id, models.Resource.resource_def_key, models.StockEntry.quantity)
            .join(models.Resource, models.Resource.id == models.StockEntry.resource_id)
            .where(models.StockEntry.source == "ocr", models.StockEntry.source_image_id.is_not(None))
        )
        for image_id, key, qty in rows:
            if key:
                confirmed.setdefault(image_id, {})[key] = qty

        for image_id, truth in confirmed.items():
            image = db.get(models.UploadImage, image_id)
            if not image:
                continue
            path = Path(image.file_path)
            path = path if path.is_file() else UPLOADS_DIR / path.name
            if not path.is_file():
                continue
            with Image.open(path) as img:
                width, height = img.size
            for item in icon_match_service.detect_items(path, (0, 0, width, height), read_number=reader):
                value = _value(item["quantity_raw"] if item["quantity_guess"] else "")
                keys = [k for k, q in truth.items() if value is not None and abs(q - value) < 1e-6]
                if len(keys) != 1:
                    continue
                x, y, s = item["box_x"], item["box_y"], item["box_width"]
                icon_match_service.add_exemplar(path, (x, y, x + s, y + s), keys[0])
                added += 1
    print(f"{added} exemplars saved to {icon_match_service.EXEMPLARS_DIR}")


if __name__ == "__main__":
    main()
