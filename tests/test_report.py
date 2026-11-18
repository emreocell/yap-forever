import unittest

from tests import toy
from yap_forever.config import USER_DIR, Credentials
from yap_forever.costmodel import Valuer
from yap_forever.favor import load_favor
from yap_forever.planner import Plan, plan
from yap_forever.report import SECTIONS, render, verdict


def sample():
    rs = [toy.recipe(1, "BS basic", 164, {toy.COPPER_BAR: 1}, (toy.STONE, 1)),
          toy.recipe(2, "Ench basic", 333, {toy.ROD: 1})]
    gd = toy.gamedata(rs)
    st = toy.stock({toy.COPPER_BAR: 5})
    m = toy.market({toy.COPPER_BAR: [(100, 100000)], toy.STONE: [(50, 3)]})
    return plan(gd, Valuer(m, gd, st), st, toy.NO_FAVOR), m, gd, st


class VerdictTests(unittest.TestCase):
    def test_verdict_now(self):
        self.assertEqual(verdict(Plan(farm={}), toy.stock()), "Switch now")

    def test_verdict_short(self):
        self.assertEqual(verdict(Plan(farm={2770: 100, 2771: 50}), toy.stock()), "Switch after a short farm")

    def test_verdict_not_yet(self):
        self.assertEqual(verdict(Plan(farm={2770: 250}), toy.stock()), "Not yet")


class RenderTests(unittest.TestCase):
    def test_report_sections_in_order(self):
        p, m, gd, st = sample()
        text = render(p, verdict(p, st), m, gd, st, toy.NO_FAVOR)
        positions = [text.index(f"## {s}\n") for s in SECTIONS]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(SECTIONS), 9)

    def test_report_has_no_secrets(self):
        creds = Credentials("myclientid", "s3cr3tvalue", "eu")
        p, m, gd, st = sample()
        text = render(p, verdict(p, st), m, gd, st, toy.NO_FAVOR)
        self.assertNotIn(creds.client_id, text)
        self.assertNotIn(creds.client_secret, text)

    def test_route_lists_steps(self):
        p, m, gd, st = sample()
        text = render(p, verdict(p, st), m, gd, st, toy.NO_FAVOR)
        self.assertIn("BS basic", text)
        self.assertIn("Ench basic", text)

    @unittest.skipUnless((USER_DIR / "favor.toml").exists(), "favor.toml not written yet")
    def test_real_favor_toml_parses(self):
        from yap_forever import gamedata
        fav = load_favor()
        self.assertTrue(fav.recipes)
        if (gamedata.GD_DIR / "Recipes.lua").exists():
            gd = gamedata.load_gamedata()
            for spell in fav.recipes:
                self.assertIn(gd.recipes[spell].skill_line, (164, 333))


if __name__ == "__main__":
    unittest.main()
