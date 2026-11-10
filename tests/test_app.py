import json
import unittest

from app import crud, schemas
from app.database import SessionLocal
from app.main import app
from tests.helpers import call


class LocalModeDoor(unittest.TestCase):
    """Local mode has no login: only this PC's own page may talk to the app."""

    def test_the_app_own_page_gets_in(self):
        for host in ("localhost:8000", "127.0.0.1:8000", "[::1]:8000", "localhost"):
            with self.subTest(host=host):
                status, _, _ = call(app, "GET", "/api/facilities", {"host": host})
                self.assertEqual(status, 200)

    def test_another_site_name_pointing_here_is_refused(self):
        # DNS rebinding: the page is evil.example, resolved to 127.0.0.1.
        for host in ("evil.example:8000", "localhost.evil.example", "evil.example"):
            with self.subTest(host=host):
                status, _, _ = call(app, "GET", "/api/facilities", {"host": host})
                self.assertEqual(status, 403)

    def test_a_post_from_another_site_is_refused(self):
        for origin in ("https://evil.example", "null", "http://localhost.evil.example"):
            with self.subTest(origin=origin):
                status, _, _ = call(app, "POST", "/api/facilities", {"origin": origin}, {"name": "x"})
                self.assertEqual(status, 403)

    def test_a_post_from_the_app_own_page_works(self):
        for origin in ("http://localhost:8000", "http://127.0.0.1:8000"):
            with self.subTest(origin=origin):
                status, _, body = call(app, "POST", "/api/facilities", {"origin": origin}, {"name": "Porta"})
                self.assertEqual(status, 201, body)

    def test_a_request_through_a_proxy_is_refused(self):
        status, _, _ = call(app, "GET", "/api/facilities", {"x-forwarded-for": "203.0.113.9"})
        self.assertEqual(status, 403)

    def test_another_machine_is_refused(self):
        status, _, _ = call(app, "GET", "/api/facilities", client=("192.168.0.50", 40000))
        self.assertEqual(status, 403)


class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db = SessionLocal()
        try:
            facility = crud.create_facility(db, schemas.FacilityCreate(name="API"))
            building = crud.create_building(db, facility.id, schemas.BuildingCreate(building_type_key="materials_factory"))
            crud.add_stock_entries(
                db,
                building.id,
                [
                    schemas.StockEntryIn(resource_name="Salvage", quantity_raw="500", resource_def_key="salvage"),
                    schemas.StockEntryIn(resource_name="Petrol", quantity_raw="40", resource_def_key="petrol", storage="tank"),
                ],
            )
            cls.facility_id, cls.building_id = facility.id, building.id
        finally:
            db.close()

    def test_answers_carry_the_security_headers(self):
        _, headers, _ = call(app, "GET", "/api/facilities")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["x-frame-options"], "DENY")
        self.assertIn("script-src 'self'", headers["content-security-policy"])

    def test_facility_stock_lists_every_building(self):
        status, _, body = call(app, "GET", f"/api/facilities/{self.facility_id}/stock")
        self.assertEqual(status, 200, body)
        entries = json.loads(body)[0]["entries"]
        self.assertEqual({(e["quantity"], e["storage"]) for e in entries}, {(500, "normal"), (40, "tank")})

    def test_a_negative_queue_cannot_hide_one_over_the_limit(self):
        slots = {"slots": [{"recipe_key": "cmat", "queue_count": 10}, {"recipe_key": "maintenance_supplies", "queue_count": -5}]}
        status, _, _ = call(app, "PUT", f"/api/buildings/{self.building_id}/production", body=slots)
        self.assertEqual(status, 422)

    def test_queues_over_the_building_limit_are_refused(self):
        status, _, _ = call(
            app, "PUT", f"/api/buildings/{self.building_id}/production", body={"slots": [{"recipe_key": "cmat", "queue_count": 6}]}
        )
        self.assertEqual(status, 422)

    def test_a_bad_quantity_gets_a_readable_message(self):
        entries = [{"resource_name": "Salvage", "resource_def_key": "salvage", "quantity_raw": "muito"}]
        status, _, body = call(app, "POST", f"/api/buildings/{self.building_id}/stock?lang=pt-BR", body=entries)
        self.assertEqual(status, 422)
        self.assertIn("muito", json.loads(body)["detail"])

    def test_uploads_only_serve_images(self):
        status, _, _ = call(app, "GET", "/uploads/algo.html")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
