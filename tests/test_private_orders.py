import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services import foxhole_data, private_orders

START = datetime(2026, 11, 8, 22, 46, tzinfo=timezone.utc)
FACTORY = SimpleNamespace(id=1, building_type_key="ammunition_factory")


def _order(inputs: dict, cycle_left: int = 0, done_before: int = 0, recipe: str = "300mm"):
    return SimpleNamespace(
        id=1,
        building_id=1,
        owner_name="Fulano",
        recipe_key=recipe,
        inputs=inputs,
        cycle_left_seconds=cycle_left,
        done_before=done_before,
        started_at=START,
        created_by=None,
    )


class Compute(unittest.TestCase):
    def setUp(self):
        recipe = foxhole_data.get_recipe("ammunition_factory", "300mm")
        self.cycle = recipe["time_seconds"]
        self.per = {io["resource"]: io["qty"] for io in private_orders.solid_inputs(recipe)}
        # Enough of everything for exactly 10 more cycles.
        self.loaded = {key: qty * 10 for key, qty in self.per.items()}

    def test_cycles_come_from_the_scarcest_input_plus_the_one_running(self):
        short = dict(self.loaded)
        scarce = next(iter(short))
        short[scarce] = self.per[scarce] * 4
        result = private_orders.compute(_order(short, cycle_left=60), FACTORY, START)
        self.assertEqual(result["total_cycles"], 5)  # 4 loaded + the one in progress
        self.assertEqual(result["limiting"], foxhole_data.resource_display_name(scarce))

    def test_ready_time_and_the_28_hours_to_retrieve(self):
        result = private_orders.compute(_order(self.loaded, cycle_left=60), FACTORY, START)
        ready = START + timedelta(seconds=60 + 10 * self.cycle)
        self.assertEqual(result["ready_at"], ready)
        self.assertEqual(result["expires_at"], ready + timedelta(hours=28))

    def test_status_follows_the_clock(self):
        order = _order(self.loaded, cycle_left=60)
        ready = START + timedelta(seconds=60 + 10 * self.cycle)
        self.assertEqual(private_orders.compute(order, FACTORY, START + timedelta(seconds=30))["status"], "running")
        self.assertEqual(private_orders.compute(order, FACTORY, ready)["status"], "ready")
        self.assertEqual(private_orders.compute(order, FACTORY, ready + timedelta(hours=28))["status"], "released")

    def test_only_finished_cycles_count_as_made(self):
        order = _order(self.loaded, cycle_left=60, done_before=7)
        made = lambda seconds: private_orders.compute(order, FACTORY, START + timedelta(seconds=seconds))["outputs"][0]["done"]
        self.assertEqual(made(59), 7)  # the running cycle hasn't delivered
        self.assertEqual(made(60), 8)
        self.assertEqual(made(60 + self.cycle - 1), 8)
        self.assertEqual(made(60 + self.cycle), 9)
        self.assertEqual(made(10**7), 7 + 11)  # never more than what was loaded

    def test_nothing_loaded_and_nothing_running_is_already_done(self):
        result = private_orders.compute(_order({}, done_before=36), FACTORY, START + timedelta(minutes=1))
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["outputs"][0]["done"], 36)

    def test_a_recipe_the_catalog_no_longer_has_does_not_break(self):
        result = private_orders.compute(_order({}, recipe="gone"), FACTORY, START)
        self.assertFalse(result["recipe_found"])
        self.assertEqual(result["status"], "running")


class Incoming(unittest.TestCase):
    def test_what_went_public_is_not_on_the_way_any_more(self):
        orders = [
            {"status": "running", "outputs": [{"resource": "300mm", "done": 9}]},
            {"status": "ready", "outputs": [{"resource": "300mm", "done": 36}]},
            {"status": "released", "outputs": [{"resource": "300mm", "done": 50}]},
        ]
        self.assertEqual(private_orders.incoming(orders), {"300mm": 45})


if __name__ == "__main__":
    unittest.main()
