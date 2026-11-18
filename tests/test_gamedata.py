import tomllib
import unittest
from pathlib import Path

from yap_forever import gamedata
from yap_forever import settings
from yap_forever.config import STATIC_DIR

FIX = Path(__file__).parent / "fixtures" / "gamedata"
REAL = settings.paths(settings.home({})).gamedata  # the player's real cache, not the test home


class GameDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gd = gamedata.load_gamedata(FIX)

    def test_parse_recipe_reagents_output(self):
        r = self.gd.recipes[2661]
        self.assertEqual(r.name, "Copper Chain Belt")
        self.assertEqual(r.skill_line, 164)
        self.assertEqual(r.reagents, {2840: 6})
        self.assertEqual(r.output, (2851, 1))
        self.assertEqual(r.thresholds, (1, 70, 90, 110))

    def test_enchant_without_item_output(self):
        self.assertIsNone(self.gd.recipes[7418].output)

    def test_required_skill_overrides_placeholder(self):
        # Orange placeholder 1; the trainer asks 30. TrainerInferred is Classic's
        # pre-Forever value and must not win.
        r = self.gd.recipes[2661]
        self.assertEqual(r.required_skill, 30)
        self.assertEqual((r.source, r.fee), ("trainer", 90))

    def test_scroll_recipe(self):
        r = self.gd.recipes[9999]
        self.assertEqual((r.source, r.scroll_item, r.required_skill), ("scroll", 5555, 80))

    def test_starter_recipe(self):
        r = self.gd.recipes[2660]
        self.assertEqual((r.source, r.fee, r.required_skill), ("starter", 0, 1))

    def test_only_bs_and_ench_kept(self):
        self.assertNotIn(2149, self.gd.recipes)
        self.assertEqual({r.skill_line for r in self.gd.recipes.values()}, {164, 333})

    def test_tools_from_spelltotems(self):
        self.assertEqual(self.gd.recipes[7418].tools, [373])
        self.assertEqual(self.gd.recipes[2661].tools, [162])
        self.assertTrue(self.gd.satisfies(11145, 374))
        self.assertFalse(self.gd.satisfies(6218, 374))
        self.assertTrue(self.gd.satisfies(6339, 373))
        self.assertEqual(self.gd.tool_items[162], 5956)

    def test_item_info_fields(self):
        i = self.gd.items[2857]
        self.assertEqual((i.name, i.quality, i.item_level, i.class_id, i.sell_price),
                         ("Runed Copper Belt", 2, 18, 4, 200))

    def test_quest_items_from_objectives(self):
        self.assertEqual(self.gd.quest_items, {2857, 3240})

    def test_trainer_ranks_and_vendor(self):
        self.assertEqual(self.gd.trainer_ranks[164][1], gamedata.Rank(225, 4500, 125, 20))
        self.assertEqual(self.gd.vendor_prices[6217], 124)

    @unittest.skipUnless((REAL / "ItemSparse.csv").exists(), "real game data not downloaded")
    def test_ore_names_match_itemsparse(self):
        names = gamedata.item_names(REAL / "ItemSparse.csv")
        with open(STATIC_DIR / "ore.toml", "rb") as f:
            ore = tomllib.load(f)
        for section in ("ore", "bars"):
            for item_id, row in ore[section].items():
                self.assertEqual(names.get(int(item_id)), row[0], f"{section} {item_id}")


if __name__ == "__main__":
    unittest.main()
