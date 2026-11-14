import unittest
import urllib.request
import uuid
from unittest import mock

from app import auth, crud, models, schemas
from app.database import SessionLocal
from app.main import app
from app.services import capture, netguard
from tests.helpers import call


class OutgoingAddresses(unittest.TestCase):
    """The capture's API address is typed by any member and called by the
    server: on the web it can't be the server's own network."""

    PRIVATE = [
        "http://127.0.0.1:8000/",
        "http://localhost/",
        "http://10.0.0.5/v1",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://100.100.100.100/",  # CGNAT, where VPN meshes live
        "http://[::1]/",
        "http://[::ffff:10.0.0.5]/",
        "ftp://8.8.8.8/",
        "http:///sem-host",
    ]

    def test_private_addresses_are_refused_on_the_web(self):
        with mock.patch.object(netguard, "public_only", return_value=True):
            for url in self.PRIVATE:
                with self.assertRaises(netguard.BlockedAddress, msg=url):
                    netguard.check_url(url)
            netguard.check_url("https://8.8.8.8/v1")  # a public one passes

    def test_local_mode_talks_to_its_own_network(self):
        for url in self.PRIVATE:
            netguard.check_url(url)

    def test_the_connection_itself_is_checked(self):
        # A name can resolve to a public address when saved and a private one later.
        with mock.patch.object(netguard, "public_only", return_value=True):
            request = urllib.request.Request("http://127.0.0.1:9/", data=b"{}")
            with self.assertRaises(OSError):
                netguard.urlopen(request, timeout=2)

    def test_redirects_are_not_followed(self):
        handler = netguard._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 302, "Found", {}, "http://10.0.0.1/"))

    def test_settings_refuse_a_private_api_address_on_the_web(self):
        with mock.patch.object(netguard, "public_only", return_value=True):
            status, _, body = call(app, "PUT", "/api/settings/capture", body={"api_base_url": "http://169.254.169.254/"})
        self.assertEqual(status, 422, body)

    def test_a_member_cannot_move_the_servers_ollama_on_the_web(self):
        with mock.patch.object(capture, "ollama_url_locked", return_value=True):
            status, _, _ = call(app, "PUT", "/api/settings/capture", body={"ollama_url": "http://10.0.0.9:11434"})
            self.assertEqual(status, 200)
            with SessionLocal() as db:
                self.assertEqual(capture.get_settings(db)["ollama_url"], capture.DEFAULTS["ollama_url"])
                self.assertIsNone(db.get(models.AppSetting, "ollama_url"))


class PrivatePrints(unittest.TestCase):
    """A print of a private facility only opens for its owner, like the rest of it."""

    def setUp(self):
        self.db = SessionLocal()
        # The tests share one database: every run gets its own people and print.
        self.owner = models.User(discord_id=uuid.uuid4().hex, username="dono")
        self.other = models.User(discord_id=uuid.uuid4().hex, username="outro")
        self.db.add_all([self.owner, self.other])
        self.db.commit()
        facility = crud.create_facility(self.db, schemas.FacilityCreate(name="Privada"))
        facility.private, facility.owner_id = True, self.owner.id
        building = crud.create_building(self.db, facility.id, schemas.BuildingCreate(name="B"))
        self.name = f"{uuid.uuid4().hex}.png"
        # Saved on another system, as on the server after the data moved.
        crud.create_upload_image(self.db, building.id, rf"E:\dados\uploads\{self.name}")
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_only_the_owner_opens_the_print(self):
        path = f"/uploads/{self.name}"
        self.assertTrue(auth._private_facility_blocked(path, {}, self.other.id))
        self.assertFalse(auth._private_facility_blocked(path, {}, self.owner.id))

    def test_other_prints_and_odd_names_pass_through(self):
        self.assertFalse(auth._private_facility_blocked(f"/uploads/{uuid.uuid4().hex}.png", {}, self.other.id))
        self.assertFalse(auth._private_facility_blocked("/uploads/%.png", {}, self.other.id))
