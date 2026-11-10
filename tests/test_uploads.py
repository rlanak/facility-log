import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from PIL import Image

from app import crud, models, schemas
from app.database import UPLOADS_DIR, SessionLocal, upload_path
from app.services import upload_cleanup
from app.services.capture import readers


class UploadPath(unittest.TestCase):
    def test_only_the_file_name_counts_whatever_system_saved_it(self):
        self.assertEqual(upload_path(r"E:\pasta\data\uploads\abc123.png"), UPLOADS_DIR / "abc123.png")
        self.assertEqual(upload_path("/data/uploads/def456.jpg"), UPLOADS_DIR / "def456.jpg")
        self.assertEqual(upload_path("ghi789.webp"), UPLOADS_DIR / "ghi789.webp")


class Cleanup(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        facility = crud.create_facility(self.db, schemas.FacilityCreate(name="Prints"))
        self.building = crud.create_building(self.db, facility.id, schemas.BuildingCreate(name="B"))
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.db.close()

    def _upload(self, name: str, age_days: int) -> models.UploadImage:
        path = UPLOADS_DIR / name
        path.write_bytes(b"png")
        image = crud.create_upload_image(self.db, self.building.id, str(path))
        image.uploaded_at = self.now - timedelta(days=age_days)
        self.db.commit()
        return image

    def test_nothing_is_deleted_unless_asked(self):
        old = self._upload("antigo-desligado.png", 400)
        with mock.patch.dict(os.environ, {"FACILITY_LOG_UPLOAD_DAYS": ""}):
            self.assertEqual(upload_cleanup.keep_days(), 0)
            self.assertEqual(upload_cleanup.purge(self.now), 0)
        self.assertTrue(upload_path(old.file_path).is_file())

    def test_old_prints_go_and_recent_ones_stay(self):
        old = self._upload("antigo.png", 45)
        recent = self._upload("recente.png", 3)
        entry = crud.add_stock_entries(
            self.db,
            self.building.id,
            [schemas.StockEntryIn(resource_name="Salvage", quantity_raw="5", resource_def_key="salvage", source_image_id=old.id)],
        )[0]
        old_id, entry_id = old.id, entry.id
        with mock.patch.dict(os.environ, {"FACILITY_LOG_UPLOAD_DAYS": "30"}):
            removed = upload_cleanup.purge(self.now)
        self.assertGreaterEqual(removed, 1)
        self.db.expire_all()
        self.assertFalse((UPLOADS_DIR / "antigo.png").exists())
        self.assertIsNone(self.db.get(models.UploadImage, old_id))
        self.assertTrue((UPLOADS_DIR / "recente.png").is_file())
        self.assertIsNotNone(self.db.get(models.UploadImage, recent.id))
        # The stock entry stays; only its pointer to the print is cleared.
        kept = self.db.get(models.StockEntry, entry_id)
        self.assertEqual(kept.quantity, 5)
        self.assertIsNone(kept.source_image_id)

    def test_files_without_a_row_follow_the_same_age(self):
        orphan = UPLOADS_DIR / "orfao.png"
        orphan.write_bytes(b"png")
        with mock.patch.dict(os.environ, {"FACILITY_LOG_UPLOAD_DAYS": "30"}):
            upload_cleanup.purge(self.now)
            self.assertTrue(orphan.is_file())  # written just now
            upload_cleanup.purge(self.now + timedelta(days=31))
        self.assertFalse(orphan.exists())


class ReaderCrops(unittest.TestCase):
    """What goes to the number reader is never bigger than a number needs."""

    @classmethod
    def setUpClass(cls):
        cls.image = UPLOADS_DIR / "tela-teste.png"
        Image.new("RGB", (2560, 1440), (30, 30, 30)).save(cls.image)

    @classmethod
    def tearDownClass(cls):
        Path(cls.image).unlink(missing_ok=True)

    def test_a_number_sized_crop_gets_the_full_upscale(self):
        self.assertEqual(readers._prepare_crop(self.image, (100, 100, 170, 124)).size, (420, 144))

    def test_a_screen_sized_crop_is_not_blown_up(self):
        crop = readers._prepare_crop(self.image, (0, 0, 2560, 1440))
        self.assertLessEqual(max(crop.size), readers.MAX_READ_SIDE)
        with Image.open(__import__("io").BytesIO(readers._crop_png(self.image, (-500, -500, 99999, 99999)))) as png:
            self.assertLessEqual(max(png.size), readers.MAX_READ_SIDE)

    def test_a_box_outside_the_image_is_brought_inside(self):
        self.assertEqual(readers._crop(self.image, (2550, 1430, 2700, 1500)).size, (10, 10))
        self.assertEqual(readers._crop(self.image, (5000, 5000, 6000, 6000)).size, (1, 1))


if __name__ == "__main__":
    unittest.main()
