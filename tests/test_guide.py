import unittest

from tests import toy
from yap_forever.guide import render_guide, source_group
from tests.test_planner import BARS, base_recipes, run

BS, ENCH = 164, 333


def guide(recipes, listings, stock=None, cap=60):
    st = stock or toy.stock()
    p = run(recipes, listings, stock=st, cap=cap)
    gd = toy.gamedata(recipes)
    return render_guide(p, gd, toy.market(listings), st)


class SourceGroupTests(unittest.TestCase):
    def test_groups(self):
        gd = toy.gamedata([])
        self.assertEqual(source_group(2836, gd), "Mining")       # Coarse Stone
        self.assertEqual(source_group(toy.COPPER_BAR, gd), "Mining")
        self.assertEqual(source_group(1210, gd), "Mining")       # Shadowgem
        self.assertEqual(source_group(4304, gd), "Skinning")     # Thick Leather
        self.assertEqual(source_group(2589, gd), "Cloth")        # Linen Cloth
        self.assertEqual(source_group(toy.DUST, gd), "Enchanting materials")
        self.assertEqual(source_group(toy.ROD, gd), "Vendor")    # vendor-sold in toy data
        self.assertEqual(source_group(toy.ODD, gd), "Drops and AH")


class GuideTests(unittest.TestCase):
    def test_sections(self):
        text = guide(base_recipes(), BARS)
        for heading in ("## Keep while levelling", "## Route", "## Money"):
            self.assertIn(heading, text)

    def test_keep_list_shows_bank_and_still_to_get(self):
        text = guide(base_recipes(), BARS, stock=toy.stock({toy.COPPER_BAR: 20}))
        row = next(l for l in text.splitlines() if l.startswith("| Copper Bar"))
        self.assertEqual([c.strip() for c in row.split("|")[2:5]], ["59", "20", "39"])

    def test_route_merges_skill_range(self):
        text = guide(base_recipes(), BARS)
        self.assertIn("**1–60** · 59× BS basic", text)

    def test_reused_craft_noted(self):
        rs = [toy.recipe(1, "Copper Rod", BS, {toy.COPPER_BAR: 1}, (toy.ROD, 1)),
              toy.recipe(2, "Ench rod", ENCH, {toy.ROD: 1})]
        text = guide(rs, {**BARS, toy.ROD: [(100000, 1000)]}, cap=40)
        self.assertIn("keep for Ench rod", text)
        self.assertIn("Copper Rod (yours)", text)

    def test_vendor_items_not_in_keep_tables(self):
        rs = [toy.recipe(1, "BS basic", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1)),
              toy.recipe(2, "Ench basic", ENCH, {toy.ROD: 1})]
        text = guide(rs, BARS)
        self.assertFalse(any(l.startswith("| Copper Rod") for l in text.splitlines()))
        self.assertIn("Buy from a vendor when you switch", text)


if __name__ == "__main__":
    unittest.main()


class ReadabilityTests(unittest.TestCase):
    def test_disenchant_events_collapse_to_one_line(self):
        rs = [toy.recipe(1, "Belt", BS, {toy.COPPER_BAR: 1}, (toy.BELT, 1)),
              toy.recipe(2, "Ench dust", ENCH, {toy.DUST: 1})]
        text = guide(rs, {**BARS, toy.DUST: [(300, 100000)]}, cap=40)
        lines = [l for l in text.splitlines() if "disenchant" in l and "Runed Copper Belt" in l]
        self.assertEqual(len(lines), 1, lines)

    def test_unnamed_recipe_shows_item_name(self):
        rs = [toy.recipe(9, "spell 9", BS, {toy.COPPER_BAR: 1}, (toy.VEST, 1)),  # unnamed: "spell <id>"
              toy.recipe(2, "Ench basic", ENCH, {toy.ROD: 1})]
        text = guide(rs, BARS)
        self.assertNotIn("spell 9", text)
        self.assertIn("× Copper Chain Vest", text)


class QuestItemNoteTests(unittest.TestCase):
    def test_quest_item_note_shows_limit(self):
        import dataclasses
        rs = [toy.recipe(1, "Vest", BS, {toy.COPPER_BAR: 1}, (toy.VEST, 1)),
              toy.recipe(2, "Ench basic", ENCH, {toy.ROD: 1})]
        st = dataclasses.replace(toy.stock(), quest_item_sales=20)
        gd = toy.gamedata(rs, quest_items=[toy.VEST])
        listings = {**BARS, toy.VEST: [(5000, 3)]}
        from yap_forever.costmodel import Valuer
        from yap_forever.planner import plan
        p = plan(gd, Valuer(toy.market(listings), gd, st), st, toy.NO_FAVOR, cap=60)
        text = render_guide(p, gd, toy.market(listings), st)
        self.assertIn("sell up to 20 on the AH (quest item), the rest to a vendor", text)
