import unittest

from tests import toy
from tests.test_planner import BARS, base_recipes, run

BS, ENCH = 164, 333


def total(steps, attr):
    out = {}
    for s in steps:
        for i, q in getattr(s, attr).items():
            out[i] = out.get(i, 0) + q
    return out


class StepMaterialsTests(unittest.TestCase):
    def test_step_materials_add_up_to_plan_totals(self):
        p = run(base_recipes(), BARS, stock=toy.stock({toy.COPPER_BAR: 50}), cap=60)
        mats = total(p.steps, "materials")
        # copper: 50 from the bank, the rest bought
        self.assertAlmostEqual(mats[toy.COPPER_BAR],
                               p.used_stock[toy.COPPER_BAR] + p.bought[toy.COPPER_BAR])
        self.assertAlmostEqual(total(p.steps, "from_stock")[toy.COPPER_BAR], 50)

    def test_reused_crafts_recorded(self):
        # Enchanting uses the Copper Rods Blacksmithing makes
        rs = [toy.recipe(1, "Copper Rod", BS, {toy.COPPER_BAR: 1}, (toy.ROD, 1)),
              toy.recipe(2, "Ench rod", ENCH, {toy.ROD: 1})]
        p = run(rs, {**BARS, toy.ROD: [(100000, 1000)]}, cap=40)
        used = total([s for s in p.steps if s.profession == ENCH], "used_made")
        self.assertGreater(used.get(toy.ROD, 0), 0)
        self.assertNotIn(toy.ROD, total(p.steps, "materials"))


if __name__ == "__main__":
    unittest.main()
