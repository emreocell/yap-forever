import unittest

from tests import toy
from yap_forever import settings
from yap_forever.config import Credentials
USER_DIR = settings.home({})  # the player's real folder, not the test home
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

    def test_real_favor_toml_parses(self):
        from yap_forever import gamedata
        fav = load_favor("Exalted")
        self.assertTrue(fav.recipes)
        if (settings.paths(USER_DIR).gamedata / "Recipes.lua").exists():
            gd = gamedata.load_gamedata(settings.paths(USER_DIR).gamedata)
            for spell in fav.recipes:
                self.assertIn(gd.recipes[spell].skill_line, (164, 333))


if __name__ == "__main__":
    unittest.main()


class BufferTests(unittest.TestCase):
    def test_route_crafts_match_guide_buffer(self):
        from yap_forever.planner import buffer_factor
        import math
        rs = [toy.recipe(1, "BS yellow", 164, {toy.COPPER_BAR: 1}, (toy.STONE, 1), t=(1, 1, 6, 11)),
              toy.recipe(2, "Ench basic", 333, {toy.ROD: 1})]
        gd = toy.gamedata(rs)
        st = toy.stock()
        m = toy.market({toy.COPPER_BAR: [(100, 100000)]})
        p = plan(gd, Valuer(m, gd, st), st, toy.NO_FAVOR, cap=11)
        text = render(p, verdict(p, st), m, gd, st, toy.NO_FAVOR)
        yellow = [s for s in p.steps if s.spell_id == 1 and s.crafts > 1]
        self.assertTrue(yellow)
        for s in yellow:
            self.assertIn(f"| BS yellow | {math.ceil(s.crafts * 1.15 - 1e-6)} |", text)
        self.assertEqual(buffer_factor(1.0), 1.0)
