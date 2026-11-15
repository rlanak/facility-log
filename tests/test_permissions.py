import os
import unittest
import uuid
from datetime import timedelta
from unittest import mock

from app import auth, crud, models, permissions, schemas
from app.database import UPLOADS_DIR, SessionLocal
from app.main import app
from app.routers import images
from app.services import capture
from tests.helpers import call


def web_mode():
    """The tests run in local mode; this makes the rules see the web one."""
    return mock.patch.object(auth.config, "client_id", "tests")


def person(db, admin: bool = False) -> auth.SessionUser:
    row = models.User(discord_id=uuid.uuid4().hex, username=f"u{uuid.uuid4().hex[:6]}")
    db.add(row)
    db.commit()
    return auth.SessionUser(id=row.id, name=row.username, avatar_url=None, is_admin=admin)


class Base(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        self.owner, self.helper, self.reader, self.admin = (
            person(self.db),
            person(self.db),
            person(self.db),
            person(self.db, admin=True),
        )
        self.facility = crud.create_facility(self.db, schemas.FacilityCreate(name="Perm"), owner_id=self.owner.id)
        self.b1 = crud.create_building(self.db, self.facility.id, schemas.BuildingCreate(name="B1"))
        self.b2 = crud.create_building(self.db, self.facility.id, schemas.BuildingCreate(name="B2"))
        self.f, self.one, self.two = self.facility.id, self.b1.id, self.b2.id
        permissions.set_permission(self.db, self.facility, self.helper.id, False, [self.one])

    def tearDown(self):
        self.db.close()

    def denied(self, user, method, path):
        with web_mode():
            return auth.write_denied(method, path, user)


class WhoMayWrite(Base):
    def test_a_member_only_reads(self):
        for method, path in [
            ("POST", f"/api/buildings/{self.one}/stock"),
            ("PUT", f"/api/buildings/{self.one}/production"),
            ("POST", f"/api/buildings/{self.one}/images"),
            ("POST", f"/api/buildings/{self.one}/private-orders"),
            ("PUT", f"/api/buildings/{self.one}/save-pin"),
            ("PUT", f"/api/facilities/{self.f}/targets"),
            ("POST", f"/api/facilities/{self.f}/reports"),
        ]:
            self.assertTrue(self.denied(self.reader, method, path), path)
            self.assertIsNone(self.denied(self.reader, "GET", path), path)

    def test_allowed_on_one_building_edits_only_that_one(self):
        self.assertIsNone(self.denied(self.helper, "POST", f"/api/buildings/{self.one}/stock"))
        self.assertIsNone(self.denied(self.helper, "PUT", f"/api/buildings/{self.one}/production"))
        self.assertIsNone(self.denied(self.helper, "DELETE", f"/api/buildings/{self.one}/stock/3"))
        self.assertTrue(self.denied(self.helper, "POST", f"/api/buildings/{self.two}/stock"))

    def test_a_print_follows_its_building(self):
        image = crud.create_upload_image(self.db, self.one, str(UPLOADS_DIR / f"{uuid.uuid4().hex}.png"))
        other = crud.create_upload_image(self.db, self.two, str(UPLOADS_DIR / f"{uuid.uuid4().hex}.png"))
        self.assertIsNone(self.denied(self.helper, "POST", f"/api/images/{image.id}/detect-stockpile"))
        self.assertTrue(self.denied(self.helper, "POST", f"/api/images/{other.id}/detect-stockpile"))

    def test_what_stays_with_the_owner(self):
        owner_only = [
            ("PUT", f"/api/facilities/{self.f}"),
            ("DELETE", f"/api/facilities/{self.f}"),
            ("POST", f"/api/facilities/{self.f}/buildings"),
            ("DELETE", f"/api/buildings/{self.one}"),
            ("PUT", f"/api/facilities/{self.f}/targets"),
            ("PUT", f"/api/facilities/{self.f}/item-origins"),
            ("POST", f"/api/facilities/{self.f}/reports"),
            ("PUT", f"/api/facilities/{self.f}/permissions"),
            ("PUT", f"/api/facilities/{self.f}/discord-webhook"),
        ]
        report = models.Report(facility_id=self.f, markdown_content="", stock_snapshot="[]")
        self.db.add(report)
        self.db.commit()
        owner_only.append(("DELETE", f"/api/reports/{report.id}"))
        for method, path in owner_only:
            self.assertIsNone(self.denied(self.owner, method, path), path)
            self.assertTrue(self.denied(self.helper, method, path), path)
            # Being admin doesn't make someone an editor.
            self.assertTrue(self.denied(self.admin, method, path), path)

    def test_every_building_includes_the_ones_added_later(self):
        permissions.set_permission(self.db, self.facility, self.helper.id, True, [])
        later = crud.create_building(self.db, self.f, schemas.BuildingCreate(name="B3"))
        self.assertIsNone(self.denied(self.helper, "POST", f"/api/buildings/{later.id}/stock"))

    def test_taking_the_permission_back_works_at_once(self):
        permissions.set_permission(self.db, self.facility, self.helper.id, False, [])
        self.assertTrue(self.denied(self.helper, "POST", f"/api/buildings/{self.one}/stock"))

    def test_a_building_of_another_facility_is_not_granted(self):
        other = crud.create_facility(self.db, schemas.FacilityCreate(name="Outra"), owner_id=self.reader.id)
        theirs = crud.create_building(self.db, other.id, schemas.BuildingCreate(name="X"))
        permissions.set_permission(self.db, self.facility, self.helper.id, False, [theirs.id])
        self.assertTrue(self.denied(self.helper, "POST", f"/api/buildings/{theirs.id}/stock"))

    def test_a_facility_with_no_owner_is_read_only_until_an_admin_hands_it_over(self):
        orphan = crud.create_facility(self.db, schemas.FacilityCreate(name="Sem dono"))
        building = crud.create_building(self.db, orphan.id, schemas.BuildingCreate(name="B"))
        for user in (self.owner, self.reader, self.admin):
            self.assertTrue(self.denied(user, "POST", f"/api/buildings/{building.id}/stock"))
            # It used to be taken by marking it private.
            self.assertTrue(self.denied(user, "PUT", f"/api/facilities/{orphan.id}"))
        self.assertTrue(self.denied(self.reader, "PUT", f"/api/facilities/{orphan.id}/owner"))
        self.assertIsNone(self.denied(self.admin, "PUT", f"/api/facilities/{orphan.id}/owner"))

    def test_what_is_global_is_the_admins(self):
        for method, path in [
            ("POST", "/api/resources"),
            ("PUT", "/api/resources/1"),
            ("DELETE", "/api/resources/1"),
            ("PUT", "/api/save/aliases"),
            ("POST", "/api/something-new"),  # a route nobody listed is closed
        ]:
            self.assertTrue(self.denied(self.owner, method, path), path)
            self.assertIsNone(self.denied(self.admin, method, path), path)

    def test_anyone_creates_a_facility_and_keeps_their_own_settings(self):
        self.assertIsNone(self.denied(self.reader, "POST", "/api/facilities"))
        self.assertIsNone(self.denied(self.reader, "PUT", "/api/settings/capture"))
        self.assertIsNone(self.denied(self.reader, "POST", "/api/save/pins"))

    def test_local_mode_has_no_restrictions(self):
        access = permissions.access_for(self.db, self.facility, None)
        self.assertTrue(access.manage and access.can_edit(self.two))

    def test_access_sent_to_the_page(self):
        with web_mode():
            self.assertEqual(
                permissions.access_for(self.db, self.facility, self.helper).as_dict(),
                {"manage": False, "admin": False, "buildings": [self.one]},
            )
            self.assertEqual(permissions.access_for(self.db, self.facility, self.owner).as_dict()["buildings"], "all")
            self.assertEqual(permissions.access_for(self.db, self.facility, self.reader).as_dict()["buildings"], [])

    def test_a_deleted_building_takes_its_permissions(self):
        crud.delete_building(self.db, self.db.get(models.Building, self.one))
        self.assertEqual(permissions.list_permissions(self.db, self.facility), [])


class Roles(unittest.TestCase):
    def test_several_admin_roles(self):
        env = {"DISCORD_ALLOWED_ROLE_IDS": "10", "DISCORD_ADMIN_ROLE_IDS": "20, 30 ,40"}
        with mock.patch.dict(os.environ, env), mock.patch.object(auth, "config", auth.Config()):
            self.assertEqual(auth.roles_grant({"10"}), (True, False))
            self.assertEqual(auth.roles_grant({"30"}), (True, True))  # an admin role lets in by itself
            self.assertEqual(auth.roles_grant({"10", "40"}), (True, True))
            self.assertEqual(auth.roles_grant({"99"}), (False, False))

    def test_session_length(self):
        for value, hours in [("", 24), ("7", 168), ("0.5", 12), ("abc", 24), ("0", 1), ("999", 720)]:
            with mock.patch.dict(os.environ, {"FACILITY_LOG_SESSION_DAYS": value}):
                self.assertEqual(auth._session_seconds(), hours * 3600, value)


class UploadLimit(Base):
    def _sent(self, n, hours_ago=0):
        for _ in range(n):
            image = crud.create_upload_image(
                self.db, self.one, str(UPLOADS_DIR / f"{uuid.uuid4().hex}.png"), uploaded_by_id=self.helper.id
            )
            image.uploaded_at = models.utcnow() - timedelta(hours=hours_ago)
        self.db.commit()

    def test_counts_one_persons_last_24_hours(self):
        self._sent(3)
        self._sent(4, hours_ago=30)
        self.assertEqual(images.uploads_in_last_day(self.db, self.helper.id), 3)
        self.assertEqual(images.uploads_in_last_day(self.db, self.reader.id), 0)

    def test_the_limit_comes_from_the_server_and_only_on_the_web(self):
        self.assertEqual(images.uploads_per_day(), 0)  # local mode
        with web_mode():
            for value, limit in [("", 10), ("25", 25), ("0", 0), ("x", 10)]:
                with mock.patch.dict(os.environ, {"FACILITY_LOG_UPLOADS_PER_DAY": value}):
                    self.assertEqual(images.uploads_per_day(), limit, value)


class OwnSettings(Base):
    def test_each_person_has_their_own_on_the_web(self):
        with web_mode():
            capture.save_settings(self.db, {"api_key": "chave-da-helper", "api_model": "m1"}, self.helper.id)
            self.assertEqual(capture.get_settings(self.db, self.helper.id)["api_key"], "chave-da-helper")
            self.assertEqual(capture.get_settings(self.db, self.reader.id)["api_key"], "")
            self.assertEqual(capture.get_settings(self.db, None)["api_key"], "")
        # Stored encrypted, like the shared ones were.
        raw = self.db.connection().exec_driver_sql(
            "SELECT value FROM user_settings WHERE user_id = ? AND key = 'api_key'", (self.helper.id,)
        ).scalar()
        self.assertNotIn("chave-da-helper", raw)

    def test_local_mode_keeps_one_for_the_app(self):
        capture.save_settings(self.db, {"api_model": "modelo-local"})
        self.assertEqual(capture.get_settings(self.db)["api_model"], "modelo-local")
        capture.save_settings(self.db, {"api_model": capture.DEFAULTS["api_model"]})


class Routes(Base):
    def test_local_mode_still_does_everything_through_the_app(self):
        status, _, _ = call(app, "PUT", f"/api/buildings/{self.one}", body={"name": "Novo nome"})
        self.assertEqual(status, 200)
        status, _, body = call(app, "GET", f"/api/facilities/{self.f}")
        self.assertEqual(status, 200)
        self.assertIn(b'"manage":true', body.replace(b" ", b""))
        status, _, _ = call(app, "PUT", f"/api/facilities/{self.f}/permissions", body={"user_id": self.reader.id, "all": True})
        self.assertEqual(status, 200)
