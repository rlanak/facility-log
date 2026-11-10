import unittest

from app.database import _RENAMED_RECIPES
from app.services import foxhole_data


class Catalog(unittest.TestCase):
    """data/foxhole/*.json. The wiki is checked by hand after a game update;
    this only catches what can be seen without it."""

    def setUp(self):
        self.resources = foxhole_data.get_resource_defs()
        self.types = foxhole_data.get_building_type_defs()

    def test_recipes_only_use_items_that_exist(self):
        for type_key, building_type in self.types.items():
            for recipe in building_type["recipes"]:
                for io in recipe["inputs"] + recipe["outputs"]:
                    if "resource" in io:
                        self.assertIn(io["resource"], self.resources, f"{type_key}/{recipe['key']}")
                        self.assertGreater(io.get("qty", 1), 0, f"{type_key}/{recipe['key']}")
                self.assertTrue(any("resource" in io for io in recipe["outputs"]), f"{type_key}/{recipe['key']}")
                self.assertGreater(recipe["time_seconds"], 0, f"{type_key}/{recipe['key']}")

    def test_recipe_keys_are_unique_in_a_building(self):
        for type_key, building_type in self.types.items():
            keys = [recipe["key"] for recipe in building_type["recipes"]]
            self.assertEqual(len(keys), len(set(keys)), type_key)

    def test_no_recipe_is_another_one_minus_an_input(self):
        # How four special-issue recipes came in twice (09/11/2026): a second
        # copy without the base weapon they are made from. Same product, same
        # amount, same time, and its inputs a strict subset of the other's.
        def shape(ios):
            return {io["resource"]: io["qty"] for io in ios if "resource" in io}

        for type_key, building_type in self.types.items():
            recipes = building_type["recipes"]
            for a in recipes:
                for b in recipes:
                    if a is b or shape(a["outputs"]) != shape(b["outputs"]) or a["time_seconds"] != b["time_seconds"]:
                        continue
                    ins_a, ins_b = shape(a["inputs"]), shape(b["inputs"])
                    subset = ins_a != ins_b and all(ins_b.get(key) == qty for key, qty in ins_a.items())
                    self.assertFalse(subset, f"{type_key}: {a['key']} is {b['key']} without an input")

    def test_liquids_say_how_many_liters_a_unit_is(self):
        for key, definition in self.resources.items():
            if definition.get("is_liquid"):
                self.assertGreater(definition.get("liters_per_unit") or 0, 0, key)

    def test_stations_accept_items_that_exist(self):
        for type_key, building_type in self.types.items():
            for key in building_type.get("accepts", []):
                self.assertIn(key, self.resources, type_key)

    def test_every_item_has_a_name_and_an_icon_file(self):
        from app.paths import APP_DIR

        for key, definition in self.resources.items():
            self.assertTrue(definition["name"].get("en"), key)
            if definition.get("icon"):
                self.assertTrue((APP_DIR / "web" / definition["icon"].lstrip("/")).is_file(), key)

    def test_removed_recipes_point_at_ones_that_exist(self):
        for old, new in _RENAMED_RECIPES.items():
            self.assertIsNone(foxhole_data.get_recipe("infantry_kit_factory", old), old)
            self.assertIsNotNone(foxhole_data.get_recipe("infantry_kit_factory", new), new)

    def test_recipes_fixed_against_the_wiki_stay_fixed(self):
        def inputs(type_key, recipe_key):
            recipe = foxhole_data.get_recipe(type_key, recipe_key)
            return {io["resource"]: io["qty"] for io in recipe["inputs"] if "resource" in io}

        self.assertEqual(inputs("ammunition_factory", "250mm_fury")["250mm_purity_shell"], 1)
        self.assertEqual(
            inputs("ammunition_factory", "250mm_purity"), {"construction_materials": 5, "heavy_explosive_powder": 24}
        )
        self.assertEqual(inputs("infantry_kit_factory", "austers_harness")["recon_camo"], 15)
        self.assertEqual(inputs("infantry_kit_factory", "lodesmans_lorica")["officialis_attire"], 3)
        self.assertEqual(inputs("infantry_kit_factory", "dusk_ce_iii")["dusk_ce_iii"], 20)


if __name__ == "__main__":
    unittest.main()
