"""Two routes side by side, trips away from home, and the cost of skipping one."""
import unittest

from tests import toy
from yap_forever.costmodel import Valuer
from yap_forever.guide import gold
from yap_forever.planner import Plan, plan

BS = 164
BARS = {toy.COPPER_BAR: [(100, 100000)]}


def route(mode, recipes, listings, bank=None, caps=None):
    gd = toy.gamedata(recipes)
    st = toy.stock(bank)
    return gd, plan(gd, Valuer(toy.market(listings), gd, st, mode=mode), st, toy.NO_FAVOR, caps=caps or {BS: 20})


class CompareTests(unittest.TestCase):
    def test_compare_shows_both_routes(self):
        from yap_forever.compare import compare
        rs = [toy.recipe(1, "BS basic", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1))]
        gd, g = route("gold", rs, BARS)
        _, v = route("value", rs, BARS)
        text = compare({"gold": g, "value": v}, gd, toy.market(BARS), toy.stock())
        self.assertIn("| | Least gold | Least total value |", text)
        self.assertIn(f"| Gold out of pocket | {gold(g.cash_total)} | {gold(v.cash_total)} |", text)
        self.assertIn("| Reached | Blacksmithing 20 | Blacksmithing 20 |", text)

    def test_compare_flags_thin_market(self):
        from yap_forever.compare import compare
        gd = toy.gamedata([])
        p = Plan(bought={toy.IRON_BAR: 6})
        text = compare({"gold": p, "value": p}, gd, toy.market({toy.IRON_BAR: [(10, 10)]}), toy.stock())
        row = next(line for line in text.splitlines() if line.startswith("| Thin markets"))
        self.assertIn("Iron Bar", row)


class TripTests(unittest.TestCase):
    def test_trips_kinds(self):
        from yap_forever.trips import trips
        gd = toy.gamedata([])
        p = Plan(ranks=[(BS, 60, 150, 450), (BS, 200, 225, 4500), (BS, 275, 300, 9000)],
                 learn_log=[(BS, 10, 1, "trainer"), (BS, 20, 2, "ah"), (BS, 30, 3, "vendor"),
                            (BS, 40, 4, "favor"), (BS, 50, 5, "quest")])
        self.assertEqual([(t.kind, t.skill) for t in trips(p, gd)],
                         [("vendor", 30), ("favor", 40), ("rank", 200), ("rank", 275)])

    def test_planner_logs_learning_and_ranks(self):
        rs = [toy.recipe(1, "BS basic", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1)),
              toy.recipe(30, "BS scroll", BS, {toy.IRON_BAR: 1}, (toy.STONE, 1), source="scroll", scroll=toy.SCROLL)]
        gd = toy.gamedata(rs)
        gd.vendor_prices[toy.SCROLL] = 500
        st = toy.stock()
        p = plan(gd, Valuer(toy.market({**BARS, toy.IRON_BAR: [(10, 100000)]}), gd, st), st, toy.NO_FAVOR,
                 caps={BS: 80})
        self.assertIn((BS, 1, 30, "vendor"), p.learn_log)
        self.assertEqual([(prof, cap) for prof, _s, cap, _f in p.ranks], [(BS, 150)])

    def test_trip_alternative_cost(self):
        from yap_forever.plan import plan_route
        from yap_forever.trips import trip_alternatives
        rs = [toy.recipe(1, "BS basic", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1)),
              toy.recipe(30, "BS scroll", BS, {toy.IRON_BAR: 1}, (toy.STONE, 1), source="scroll", scroll=toy.SCROLL)]
        gd = toy.gamedata(rs)
        gd.vendor_prices[toy.SCROLL] = 500
        st, m = toy.stock(), toy.market({**BARS, toy.IRON_BAR: [(10, 100000)]})
        args = (gd, m, st, toy.NO_FAVOR, {BS: 40}, {}, "gold", {})
        base = plan_route(*args)
        skip = plan_route(*args, exclude=frozenset({30}))
        alts = trip_alternatives(base, *args)
        self.assertEqual(alts, {30: skip.cash_total - base.cash_total})
        self.assertGreater(alts[30], 0)


if __name__ == "__main__":
    unittest.main()


class LeastGoldGuardTests(unittest.TestCase):
    def test_least_gold_never_costs_more_gold(self):
        from yap_forever.compare import compare, settle_routes
        gold_route, value_route = Plan(cash_total=500, economic_total=900), Plan(cash_total=400, economic_total=700)
        routes, same = settle_routes({"gold": gold_route, "value": value_route})
        self.assertIs(routes["gold"], value_route)
        self.assertTrue(same)
        text = compare(routes, toy.gamedata([]), toy.market(), toy.stock(), same=same)
        self.assertIn("The least-total-value route also spends the least gold", text)

    def test_routes_kept_when_gold_route_is_cheaper(self):
        from yap_forever.compare import settle_routes
        g, v = Plan(cash_total=300), Plan(cash_total=400)
        self.assertEqual(settle_routes({"gold": g, "value": v}), ({"gold": g, "value": v}, False))
