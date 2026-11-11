import json
import re
import unittest
from html.parser import HTMLParser

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


class _Loaded(HTMLParser):
    """What a page loads: every <script src>, <link href> and <img src>, and
    whether any <script> carries its code inline."""

    def __init__(self):
        super().__init__()
        self.urls: list[str] = []
        self.inline_scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and "src" not in attrs:
            self.inline_scripts += 1
        url = attrs.get("src") if tag in ("script", "img") else attrs.get("href") if tag == "link" else None
        if url:
            self.urls.append(url)


class PageNeedsNoOtherSite(unittest.TestCase):
    """Local mode must open with its full look with no internet, and no script
    from someone else's server may run in a logged-in session: Tailwind and
    the heading font are copies in web/vendor/, not a CDN."""

    @staticmethod
    def _own_path(url: str) -> bool:
        return url.startswith("/") and not url.startswith("//")

    def test_scripts_styles_and_fonts_only_from_the_app(self):
        _, headers, _ = call(app, "GET", "/")
        rules = dict(rule.strip().split(" ", 1) for rule in headers["content-security-policy"].split(";"))
        self.assertEqual(rules["default-src"], "'self'")
        self.assertEqual(rules["script-src"], "'self'")
        self.assertEqual(rules["style-src"], "'self' 'unsafe-inline'")
        self.assertEqual(rules["font-src"], "'self'")

    def test_the_page_loads_only_files_the_app_serves(self):
        status, _, body = call(app, "GET", "/")
        self.assertEqual(status, 200)
        page = _Loaded()
        page.feed(body.decode("utf-8"))
        self.assertEqual(page.inline_scripts, 0, "the CSP allows no inline <script>")
        self.assertTrue(any("tailwind" in url for url in page.urls), page.urls)
        for url in page.urls:
            with self.subTest(url=url):
                self.assertTrue(self._own_path(url), "loaded from another site")
                status, _, _ = call(app, "GET", url)
                self.assertEqual(status, 200)

    def test_the_heading_font_files_are_served(self):
        status, headers, body = call(app, "GET", "/vendor/saira-condensed.css")
        self.assertEqual(status, 200)
        self.assertIn("text/css", headers["content-type"])
        fonts = re.findall(r"url\(\s*[\"']?([^\"')]+)", body.decode("utf-8"))
        self.assertEqual(len(fonts), 9)  # weights 500/600/700 x latin, latin-ext, vietnamese
        for font in fonts:
            with self.subTest(font=font):
                self.assertNotIn(":", font, "loaded from another site")
                status, _, data = call(app, "GET", f"/vendor/{font}")
                self.assertEqual(status, 200)
                self.assertEqual(data[:4], b"wOF2")


class BrowserCache(unittest.TestCase):
    """The app's own files are never cached (an update must show up at once);
    the downloaded ones in web/vendor/<name>/ never change, so they are."""

    def test_only_the_downloaded_vendor_files_are_kept_by_the_browser(self):
        kept = ("/vendor/tailwindcss/tailwind-3.4.17.js", "/vendor/saira-condensed/saira-condensed-600-latin.woff2")
        fresh = ("/", "/js/app.js", "/css/style.css", "/vendor/saira-condensed.css", "/vendor/README.md")
        for path in kept:
            with self.subTest(path=path):
                status, headers, _ = call(app, "GET", path)
                self.assertEqual(status, 200)
                self.assertIn("immutable", headers["cache-control"])
        for path in fresh:
            with self.subTest(path=path):
                status, headers, _ = call(app, "GET", path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["cache-control"], "no-store")

    def test_a_missing_vendor_file_is_not_cached(self):
        status, headers, _ = call(app, "GET", "/vendor/tailwindcss/nope.js")
        self.assertEqual(status, 404)
        self.assertNotIn("immutable", headers.get("cache-control", ""))


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
