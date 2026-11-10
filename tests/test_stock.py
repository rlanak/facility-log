import unittest
from datetime import datetime, timedelta, timezone

from app import crud, models, schemas
from app.database import Base, SessionLocal, apply_migrations, engine

Base.metadata.create_all(bind=engine)
apply_migrations()


def _entry(name, qty, key=None, **more):
    return schemas.StockEntryIn(resource_name=name, quantity_raw=qty, resource_def_key=key, **more)


class AddStockEntries(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        facility = crud.create_facility(self.db, schemas.FacilityCreate(name="Teste"))
        self.building = crud.create_building(
            self.db, facility.id, schemas.BuildingCreate(building_type_key="materials_factory")
        )
        crud.add_stock_entries(self.db, self.building.id, [_entry("Salvage", "31900", "salvage")])

    def tearDown(self):
        self.db.close()

    def _stock(self):
        return {
            (e.resource.resource_def_key or e.resource.name, e.storage): e.quantity
            for e in crud.get_current_stock_for_building(self.db, self.building.id)
        }

    def test_a_refused_line_saves_nothing_at_all(self):
        batch = [
            _entry("Salvage", "777", "salvage"),
            _entry("Recurso Novo Do Teste", "5"),  # creating it used to commit the line above
            _entry("Petrol", "9999", "petrol", storage="tank"),  # over the 5000L tank: refused
        ]
        with self.assertRaises(ValueError):
            crud.add_stock_entries(self.db, self.building.id, batch)
        self.assertEqual(self._stock(), {("salvage", "normal"): 31900})
        self.assertIsNone(crud.get_resource_by_name(self.db, "Recurso Novo Do Teste"))

    def test_the_session_still_works_after_a_refusal(self):
        with self.assertRaises(ValueError):
            crud.add_stock_entries(self.db, self.building.id, [_entry("Salvage", "abc", "salvage")])
        crud.add_stock_entries(self.db, self.building.id, [_entry("Salvage", "1,5k", "salvage")])
        self.assertEqual(self._stock()[("salvage", "normal")], 1500)

    def test_quantities_that_would_break_later_reads_are_refused(self):
        for raw in ("9" * 400, "2000000000", "abc", ""):
            with self.subTest(raw=raw[:12]):
                with self.assertRaises(ValueError):
                    crud.add_stock_entries(self.db, self.building.id, [_entry("Salvage", raw, "salvage")])
        self.assertEqual(self._stock()[("salvage", "normal")], 31900)

    def test_a_full_tank_is_accepted(self):
        crud.add_stock_entries(self.db, self.building.id, [_entry("Petrol", "100", "petrol", storage="tank")])
        self.assertEqual(self._stock()[("petrol", "tank")], 100)

    def test_save_entries_keep_the_time_the_game_read_them(self):
        seen = datetime.now(timezone.utc) - timedelta(hours=5)
        created = crud.add_stock_entries(
            self.db, self.building.id, [_entry("Salvage", "100", "salvage", source="save", recorded_at=seen)]
        )
        stored = created[0].recorded_at.replace(tzinfo=timezone.utc)
        self.assertLess(abs((stored - seen).total_seconds()), 1)

    def test_a_time_that_makes_no_sense_is_logged_as_now(self):
        now = datetime.now(timezone.utc)
        for odd in (now + timedelta(days=2), datetime(1, 1, 1, tzinfo=timezone.utc)):
            with self.subTest(odd=odd.year):
                created = crud.add_stock_entries(
                    self.db, self.building.id, [_entry("Salvage", "100", "salvage", recorded_at=odd)]
                )
                stored = created[0].recorded_at.replace(tzinfo=timezone.utc)
                self.assertLess(abs((stored - now).total_seconds()), 30)

    def test_zero_missing_zeroes_only_ordinary_stock_not_listed(self):
        crud.add_stock_entries(
            self.db,
            self.building.id,
            [_entry("Coke", "50", "coke"), _entry("Petrol", "40", "petrol", storage="tank")],
        )
        crud.add_stock_entries(self.db, self.building.id, [_entry("Salvage", "10", "salvage")], zero_missing=True)
        self.assertEqual(
            self._stock(), {("salvage", "normal"): 10, ("coke", "normal"): 0, ("petrol", "tank"): 40}
        )


class Schemas(unittest.TestCase):
    def test_a_queue_count_is_never_negative(self):
        with self.assertRaises(ValueError):
            schemas.ProductionSlot(recipe_key="cmat", queue_count=-5)

    def test_storage_is_tank_or_normal(self):
        with self.assertRaises(ValueError):
            schemas.StockEntryIn(resource_name="x", quantity_raw="1", storage="shelf")


if __name__ == "__main__":
    unittest.main()
