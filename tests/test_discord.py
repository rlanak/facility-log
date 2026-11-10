import unittest
from datetime import datetime, timedelta, timezone

from app.services import discord_dashboard as dd
from app.services import foxhole_data

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def _slot(recipe: str, name: str, running: bool, missing=()):
    return {
        "recipe_key": recipe,
        "queue_count": 5,
        "cycle_seconds": 25,
        "cycles_done": 5,
        "max_cycles": 5,
        "running": running,
        "empty_at": NOW - timedelta(hours=1),
        "produced": [{"resource": recipe, "name": name, "qty": 5}],
        "missing": [foxhole_data.resource_display_name(k) for k in missing],
        "missing_keys": list(missing),
    }


def _factory(index: int, running: bool) -> dict:
    lacking = () if running else ("heavy_explosive_powder", "construction_materials")
    stock = {"construction_materials": 300, "heavy_explosive_powder": 10}
    return {
        "id": index,
        "name": f"Ammunition Factory {index:02d}",
        "building_type_key": "ammunition_factory",
        "location": "Westgate G5",
        "storage": False,
        "logged": dict(stock),
        "projected": dict(stock),
        "last_logged_at": NOW - timedelta(hours=2),
        "elapsed_seconds": 7200,
        "slots": [_slot("120mm", "120mm", running, lacking), _slot("150mm", "150mm", running, lacking)],
    }


STATION = {
    "id": 99,
    "name": "MTS01 - Norte",
    "building_type_key": "material_transfer_station",
    "location": "Westgate G5",
    "storage": True,
    "logged": {"heavy_explosive_powder": 5000, "construction_materials": 9000},
    "projected": {"heavy_explosive_powder": 5000, "construction_materials": 9000},
    "last_logged_at": NOW,
    "elapsed_seconds": 0,
    "slots": [],
}


def _targets(count: int) -> list[dict]:
    keys = list(foxhole_data.get_resource_defs())[:count]
    return [
        {
            "resource_def_key": key,
            "name": foxhole_data.resource_display_name(key),
            "target": 1000,
            "logged": 100,
            "projected": 150 + 30 * i,
            "incoming": 0,
        }
        for i, key in enumerate(keys)
    ]


class Embed(unittest.TestCase):
    """Discord refuses an embed over 6000 characters — the edit fails and the
    panel freezes, exactly when a lot is stopped and it matters most."""

    def test_stays_under_the_limit_however_much_is_stopped(self):
        for factories in (1, 8, 14, 21, 30):
            with self.subTest(factories=factories):
                data = {
                    "now": NOW,
                    "buildings": [_factory(i, running=False) for i in range(1, factories + 1)] + [STATION],
                    "targets": _targets(24),
                    "private_orders": [],
                }
                embed = dd.build_embed("FAC", data, "pt-BR", "pt-BR")
                self.assertLessEqual(dd._embed_size(embed), 6000)
                self.assertLessEqual(len(embed["fields"]), 25)
                for field in embed["fields"]:
                    self.assertLessEqual(len(field["value"]), 1024)
                    self.assertTrue(field["value"])

    def test_buildings_left_out_are_counted(self):
        data = {
            "now": NOW,
            "buildings": [_factory(i, running=False) for i in range(1, 31)],
            "targets": _targets(24),
            "private_orders": [],
        }
        embed = dd.build_embed("FAC", data, "pt-BR", "pt-BR")
        shown = sum(1 for field in embed["fields"] if field["name"].startswith("🏭"))
        more = next(field["value"] for field in embed["fields"] if field["name"] == "…")
        self.assertIn(str(30 - shown), more)

    def test_a_small_facility_keeps_everything(self):
        data = {"now": NOW, "buildings": [_factory(1, running=True), STATION], "targets": _targets(2), "private_orders": []}
        embed = dd.build_embed("FAC", data, "pt-BR", "pt-BR")
        names = [field["name"] for field in embed["fields"]]
        self.assertTrue(any(name.startswith("🗄️") for name in names))  # stations
        self.assertIn("📦", embed["fields"][1]["value"])  # stock line of the building


class ClipLines(unittest.TestCase):
    def test_never_half_a_line(self):
        lines = [f"`▰▰▰▱▱` **Item {i}** ≈ 150 de 1k · <t:1789487694:R>" for i in range(40)]
        text = dd._clip_lines(lines, 300, lambda hidden: f"… +{hidden}")
        self.assertLessEqual(len(text), 300)
        kept = text.split("\n")
        self.assertEqual(kept[:-1], lines[: len(kept) - 1])
        self.assertEqual(kept[-1], f"… +{40 - (len(kept) - 1)}")

    def test_groups_stay_together(self):
        lines = [text for i in range(10) for text in (f"✅ **Ordem {i}**", "　`▰▰▰` 30/36 · pronta <t:1789487694:R>")]
        kept = dd._clip_lines(lines, 200, lambda hidden: f"… +{hidden}", group=2).split("\n")
        self.assertEqual((len(kept) - 1) % 2, 0)

    def test_short_text_is_untouched(self):
        self.assertEqual(dd._clip_lines(["a", "b"], 100, lambda hidden: "…"), "a\nb")


if __name__ == "__main__":
    unittest.main()
