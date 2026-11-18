import tomllib
import unittest

from yap_forever import disenchant as de
from yap_forever import gamedata
from yap_forever import settings
from yap_forever.config import STATIC_DIR
from yap_forever.gamedata import ItemInfo
from yap_forever.prices import Market

REAL = settings.paths(settings.home({})).gamedata  # the player's real cache, not the test home


def item(ilvl, cls=4, quality=2):
    return ItemInfo(1, "x", quality, ilvl, cls, 100, 500)


class DisenchantTests(unittest.TestCase):
    def test_skill_gate(self):
        # Forever: no gate up to item level 44, seen in play (game-rules.md).
        for ilvl in (20, 22, 40, 44, 45):
            self.assertEqual(de.de_skill_needed(ilvl), 1, ilvl)
        # Higher bands are not confirmed yet and keep the Classic gate.
        self.assertEqual(de.de_skill_needed(46), 150)
        self.assertEqual(de.de_skill_needed(60), 200)

    def test_skillup_thresholds_match_play(self):
        # game-rules.md: about 19 disenchants to reach 20, 46 to 40, 73 to 50, 190 to 60.
        self.assertEqual(de.DE_THRESHOLDS, (1, 20, 40, 60))
        from yap_forever.costmodel import skillup_chance
        total, at = 0.0, {}
        for s in range(1, 60):
            total += 1 / skillup_chance(s, de.DE_THRESHOLDS)
            at[s + 1] = total
        self.assertEqual(round(at[20]), 19)
        self.assertEqual(round(at[40]), 46)
        self.assertEqual(round(at[50]), 73)
        self.assertEqual(round(at[60]), 190)

    def test_armor_yield(self):
        y = de.de_yield(item(22))
        self.assertEqual(set(y), {10940, 10998, 10978})
        self.assertAlmostEqual(y[10940], 3.75)
        self.assertAlmostEqual(y[10998], 0.225)
        self.assertAlmostEqual(y[10978], 0.1)

    def test_weapon_swaps_odds(self):
        y = de.de_yield(item(22, cls=2))
        self.assertAlmostEqual(y[10940], 0.15 * 5)    # dust at the armor essence chance
        self.assertAlmostEqual(y[10998], 0.75 * 1.5)  # essence at the armor dust chance
        self.assertAlmostEqual(y[10978], 0.1)

    def test_common_quality_no_yield(self):
        self.assertEqual(de.de_yield(item(22, quality=1)), {})
        self.assertEqual(de.de_yield(item(22, cls=7)), {})

    def test_de_value_uses_net_sell(self):
        m = Market({10940: [(300, 10)], 10998: [(1000, 5)], 10978: [(2000, 1)]})
        items = {10940: ItemInfo(10940, "Strange Dust", 1, 25, 7, 10, 0)}
        # 3.75*285 + 0.225*950 + 0.1*1900
        self.assertEqual(de.de_value(item(22), m, items), int(3.75 * 285 + 0.225 * 950 + 0.1 * 1900))

    def test_de_value_falls_back_to_vendor(self):
        items = {10940: ItemInfo(10940, "Strange Dust", 1, 25, 7, 10, 0)}
        self.assertEqual(de.de_value(item(22), Market({}), items), int(3.75 * 10))

    @unittest.skipUnless((REAL / "ItemSparse.csv").exists(), "real game data not downloaded")
    def test_de_names_match_itemsparse(self):
        names = gamedata.item_names(REAL / "ItemSparse.csv")
        with open(STATIC_DIR / "disenchant.toml", "rb") as f:
            bands = tomllib.load(f)["band"]
        for b in bands:
            for kind in ("dust", "essence", "shard"):
                if kind in b:
                    self.assertEqual(names.get(b[kind][0]), b[kind][1], b[kind])


if __name__ == "__main__":
    unittest.main()


class NoDisenchantTests(unittest.TestCase):
    def test_flagged_item_yields_nothing(self):
        wand = ItemInfo(11288, "Greater Magic Wand", 2, 23, 2, 100, 500, no_disenchant=True)
        self.assertEqual(de.de_yield(wand), {})

    @unittest.skipUnless((REAL / "ItemSparse.csv").exists(), "real game data not downloaded")
    def test_real_flags(self):
        items = gamedata.load_gamedata(REAL).items
        self.assertTrue(items[11288].no_disenchant)   # Greater Magic Wand (Enchanting craft)
        self.assertFalse(items[2857].no_disenchant)   # Runed Copper Belt (Blacksmithing green)
