import re
import unittest
from datetime import datetime

from app.services import material_chain
from app.services import report_generator as rg
from tests.helpers import Row, building, entry, resource


class DiscordParts(unittest.TestCase):
    """Hard rule: a part pasted into Discord never passes 2000 characters."""

    def test_a_block_longer_than_one_message_is_cut_at_line_breaks(self):
        long_block = "🏭 Produção necessária:\n" + "\n".join(f"• item {i}: " + "x" * 70 for i in range(60))
        paragraphs = ["cabeçalho", "total\n• a\n• b", long_block]
        parts = rg.split_for_discord(paragraphs)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), rg.DISCORD_LIMIT)
        # Nothing lost, nothing reordered, no line broken in two.
        lines = [line for part in parts for line in part.split("\n") if line and not line.startswith("**Parte")]
        expected = [line for paragraph in paragraphs for line in paragraph.split("\n")]
        self.assertEqual(lines, expected)

    def test_blocks_that_fit_stay_whole(self):
        paragraphs = ["cabeçalho", "x" * 900, "y" * 1500]
        parts = rg.split_for_discord(paragraphs)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[1].endswith("y" * 1500))

    def test_a_short_report_is_one_message_without_part_label(self):
        self.assertEqual(rg.split_for_discord(["cabeçalho", "estoque", "foco"]), ["cabeçalho\n\nestoque\n\nfoco"])

    def test_a_list_title_is_not_left_alone_at_the_end_of_a_part(self):
        bullet = "• " + "a" * 38  # 40 characters
        chunks = rg._split_long("\n".join([bullet, bullet, "Título:", bullet, bullet]), 100)
        self.assertFalse(chunks[0].endswith("Título:"))
        self.assertTrue(chunks[1].startswith("Título:\n• "))
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 100)

    def test_one_endless_line_is_still_cut(self):
        for chunk in rg._split_long("z" * 4500, 2000):
            self.assertLessEqual(len(chunk), 2000)


class MetaChain(unittest.TestCase):
    def setUp(self):
        self.cmat = resource(1, "construction_materials")
        self.shell = resource(2, "120mm")
        self.powder = resource(3, "heavy_explosive_powder", farmable=True)
        self.salvage = resource(4, "salvage", farmable=True)
        self.resources = [self.cmat, self.shell, self.powder, self.salvage]

    def _cmat_cycles(self, cmats_in_stock: float) -> int:
        station = building(1, "material_transfer_station")
        ammo = building(2, "ammunition_factory")
        stock = {station: [entry(self.cmat, cmats_in_stock)], ammo: []}
        targets = {self.cmat.id: 1000.0, self.shell.id: 100.0}  # 100x 120mm take 200 Cmats
        text = rg.build_recommendation_block(
            stock, rg._aggregate_resource_totals(stock), self.resources, targets, "en-US", "en-US", bulleted=True
        )
        found = re.search(r"Construction Materials: (\d+) cycles", text)
        return int(found.group(1)) if found else 0

    def test_a_reached_meta_still_holds_its_stock(self):
        # One Cmat short of its own Meta: 1 + the 200 the shells need.
        self.assertEqual(self._cmat_cycles(999), 201)
        # Meta reached: the shells' 200 are still missing. (This used to say
        # 0 — the chain spent the Meta's own stock.)
        self.assertEqual(self._cmat_cycles(1000), 200)
        # Only what's above the Meta is free for the chain.
        self.assertEqual(self._cmat_cycles(1150), 50)
        self.assertEqual(self._cmat_cycles(1200), 0)

    def test_a_meta_takes_from_factories_before_stations(self):
        # 600 Cmats in the factory that makes them + 600 in the station. The
        # Meta (1000) must hold the factory's first, leaving 200 in the
        # station — the only place the ammunition recipe can take them from.
        station = building(1, "material_transfer_station")
        factory = building(2, "materials_factory", [("cmat", 5)])
        ammo = building(3, "ammunition_factory")
        stock = {1: {"construction_materials": 600}, 2: {"construction_materials": 600}, 3: {}}
        result = material_chain.resolve_requirements(
            [("construction_materials", 1000), ("120mm", 100)],
            stock,
            [station, factory, ammo],
            material_chain.active_recipes_by_output([station, factory, ammo]),
            farmable_keys={"salvage", "heavy_explosive_powder"},
        )
        self.assertNotIn(("materials_factory", "cmat"), result["production"])
        self.assertEqual(result["production"][("ammunition_factory", "120mm")], 100)


class WholeReport(unittest.TestCase):
    def test_every_part_fits_with_many_metas(self):
        keys = [
            "120mm", "150mm", "300mm", "75mm", "94_5mm", "250mm_fury_shell", "flame_ammo", "mortar_shell", "rpg_ammo",
            "construction_materials", "processed_construction_materials", "assembly_materials_1", "assembly_materials_2",
            "assembly_materials_3", "assembly_materials_4", "salvage", "components", "coal", "sulfur",
        ]
        resources = [resource(i + 1, key) for i, key in enumerate(keys)]
        by_key = {r.resource_def_key: r for r in resources}
        ammo = building(1, "ammunition_factory", [("120mm", 2)], name="Ammunition Factory")
        factory = building(2, "materials_factory", [("cmat", 3)], name="Materials Factory")
        stock = {ammo: [entry(by_key["construction_materials"], 300)], factory: [entry(by_key["salvage"], 5000)]}
        targets = {r.id: 500.0 for r in resources[:15]}
        report = rg.generate_report(
            Row(name="FAC", id=1), stock, resources, targets, now=datetime(2026, 11, 10, 12, 0).astimezone()
        )
        self.assertGreater(len(report["parts"]), 1)
        for part in report["parts"]:
            self.assertLessEqual(len(part), rg.DISCORD_LIMIT)
        # The saved text gives the same parts back when the History reopens it.
        again = rg.split_for_discord(report["discord_content"].split("\n\n"))
        self.assertEqual(again, report["parts"])


if __name__ == "__main__":
    unittest.main()
