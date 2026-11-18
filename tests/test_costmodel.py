import dataclasses
import unittest

from tests import toy
from yap_forever.costmodel import Pools, Valuer, skillup_chance


class ChanceTests(unittest.TestCase):
    def test_chance_values(self):
        t = (1, 70, 90, 110)
        self.assertEqual(skillup_chance(50, t), 1.0)
        self.assertEqual(skillup_chance(70, t), 1.0)
        self.assertEqual(skillup_chance(90, t), 0.5)
        self.assertEqual(skillup_chance(100, t), 0.25)
        self.assertEqual(skillup_chance(110, t), 0.0)
        self.assertEqual(skillup_chance(0, t), 0.0)


class ValuerTests(unittest.TestCase):
    def valuer(self, listings=None, stock=None, quest=()):
        gd = toy.gamedata([], quest_items=quest)
        return Valuer(toy.market(listings), gd, stock or toy.stock())

    def test_stock_used_first_cash_zero(self):
        v = self.valuer({toy.COPPER_BAR: [(100, 50)]}, toy.stock({toy.COPPER_BAR: 10}))
        pools = Pools.from_stock(v.stock)
        c = v.take(toy.COPPER_BAR, 6, pools, skills={})
        self.assertEqual((c.cash, c.economic), (0, 6 * 95))
        self.assertEqual(pools.stock[toy.COPPER_BAR], 4)

    def test_buys_after_stock_runs_out(self):
        v = self.valuer({toy.COPPER_BAR: [(100, 50)]}, toy.stock({toy.COPPER_BAR: 2}))
        pools = Pools.from_stock(v.stock)
        c = v.take(toy.COPPER_BAR, 5, pools, skills={})
        self.assertEqual(c.cash, 300)
        self.assertEqual(c.economic, 2 * 95 + 300)
        self.assertEqual(pools.bought[toy.COPPER_BAR], 3)

    def test_marginal_buy_walks_book(self):
        v = self.valuer({toy.COPPER_BAR: [(10, 2), (50, 5)]})
        pools = Pools.from_stock(v.stock)
        self.assertEqual(v.take(toy.COPPER_BAR, 2, pools, skills={}).cash, 20)
        self.assertEqual(v.take(toy.COPPER_BAR, 1, pools, skills={}).cash, 50)

    def test_vendor_reagent_uses_vendor_price(self):
        v = self.valuer()
        c = v.take(toy.ROD, 3, Pools.from_stock(v.stock), skills={})
        self.assertEqual(c.cash, 372)

    def test_unpriceable_returns_none(self):
        v = self.valuer()
        self.assertIsNone(v.take(toy.ODD, 1, Pools.from_stock(v.stock), skills={}))

    def test_peek_does_not_change_pools(self):
        v = self.valuer({toy.COPPER_BAR: [(100, 50)]}, toy.stock({toy.COPPER_BAR: 10}))
        pools = Pools.from_stock(v.stock)
        v.take(toy.COPPER_BAR, 6, pools, skills={}, commit=False)
        self.assertEqual(pools.stock[toy.COPPER_BAR], 10)

    def test_stock_no_market_uses_vendor_sell(self):
        v = self.valuer(stock=toy.stock({toy.VEST: 2}))
        c = v.take(toy.VEST, 2, Pools.from_stock(v.stock), skills={})
        self.assertEqual((c.cash, c.economic), (0, 40))

    def test_farmable_bar_cash_zero(self):
        v = self.valuer({toy.IRON_BAR: [(60, 100)]}, toy.stock(mining=171))
        pools = Pools.from_stock(v.stock)
        c = v.take(toy.IRON_BAR, 3, pools, skills={})
        self.assertEqual((c.cash, c.economic), (0, 3 * 57))
        self.assertEqual(pools.farmed[toy.IRON_BAR], 3)

    def test_unfarmable_bar_bought(self):
        v = self.valuer({toy.IRON_BAR: [(60, 100)]}, toy.stock(mining=100))
        c = v.take(toy.IRON_BAR, 3, Pools.from_stock(v.stock), skills={})
        self.assertEqual(c.cash, 180)

    def test_mining_goal_makes_bar_farmable(self):
        st = dataclasses.replace(toy.stock(mining=100), mining_goal=171)
        v = self.valuer({toy.IRON_BAR: [(60, 100)]}, st)
        c = v.take(toy.IRON_BAR, 3, Pools.from_stock(v.stock), skills={})
        self.assertEqual(c.cash, 0)

    def test_made_items_cost_nothing(self):
        v = self.valuer({toy.COPPER_BAR: [(100, 50)]})
        pools = Pools.from_stock(v.stock)
        pools.made[toy.COPPER_BAR] = 4
        self.assertEqual(v.take(toy.COPPER_BAR, 4, pools, skills={}).economic, 0)

    def test_ah_value_capped_at_5_units(self):
        v = self.valuer({toy.VEST: [(1000, 50)]})
        self.assertEqual(v.output_value(toy.VEST, 0), 950)
        self.assertEqual(v.output_value(toy.VEST, 5), 20)  # vendor price after 5

    def test_quest_items_not_capped(self):
        v = self.valuer({toy.VEST: [(1000, 50)]}, quest=[toy.VEST])
        self.assertEqual(v.output_value(toy.VEST, 6), 950)

    def test_output_value_counts_disenchant(self):
        v = self.valuer({toy.DUST: [(300, 100)]})
        # Belt ilvl 22 armor: 3.75 dust at its AH buy price 300 (a material you'd otherwise buy)
        # + essence/shard at vendor (30, 50)
        self.assertEqual(v.output_value(toy.BELT, 10), int(3.75 * 300 + 0.225 * 30 + 0.1 * 50))


if __name__ == "__main__":
    unittest.main()


class StoneTests(unittest.TestCase):
    COARSE, HEAVY = 2836, 2838

    def test_stone_farmable_with_mining(self):
        gd = toy.gamedata([])
        v = Valuer(toy.market({self.COARSE: [(50, 100)]}), gd, toy.stock(mining=100))
        self.assertTrue(v.farmable(self.COARSE))
        self.assertFalse(v.farmable(self.HEAVY))
        pools = Pools.from_stock(v.stock)
        c = v.take(self.COARSE, 4, pools, skills={})
        self.assertEqual(c.cash, 0)
        self.assertEqual(pools.farmed[self.COARSE], 4)

    def test_farmed_stone_listed_as_mined(self):
        from yap_forever.costmodel import bars_to_ore
        self.assertEqual(bars_to_ore({self.COARSE: 10, toy.COPPER_BAR: 2}), {self.COARSE: 10, 2770: 2})


class QuestSalesLimitTests(unittest.TestCase):
    def valuer(self, limit):
        gd = toy.gamedata([], quest_items=[toy.VEST])
        st = dataclasses.replace(toy.stock(), quest_item_sales=limit)
        return Valuer(toy.market({toy.VEST: [(500, 3)]}), gd, st)

    def test_quest_item_limit(self):
        v = self.valuer(10)
        self.assertIn("ah", v.output_options(toy.VEST, 9))
        self.assertNotIn("ah", v.output_options(toy.VEST, 10))

    def test_no_limit_by_default(self):
        self.assertIn("ah", self.valuer(None).output_options(toy.VEST, 500))

    def test_sale_value_uses_limit(self):
        from yap_forever.planner import sale_value
        v = self.valuer(10)
        # 10 on the AH at 475 net, 10 to a vendor at 20
        self.assertEqual(sale_value(v, v.gd, toy.VEST, 20), 10 * 475 + 10 * 20)
