"""Shopping list, mailbox trips and what to bring to a remote trainer (ported from scripts/shopping.py)."""
import unittest

from tests import toy
from yap_forever.planner import Plan, Step

BS = 164
S, T, L, K, G = toy.COPPER_BAR, toy.IRON_BAR, toy.ROD, toy.STONE, toy.VEST


def orange(plan):
    """Mark every step as orange (no buffer), as the old script's self-checks assumed."""
    for st in plan.steps:
        st.buffered = st.crafts
    return plan


def chain_gd():
    """L from 3 S; K from 1 L; G from 1 L and 1 T (all orange: no buffer)."""
    return toy.gamedata([toy.recipe(40, "Make L", BS, {S: 3}, (L, 1)), toy.recipe(41, "Make K", BS, {L: 1}, (K, 1)),
                         toy.recipe(42, "Make G", BS, {L: 1, T: 1}, (G, 1))])


def chain_plan():
    return orange(Plan(steps=[Step(BS, 1, 11, 40, "Make L", 10, 0, 0, {S: 30}),
                       Step(BS, 11, 16, 41, "Make K", 5, 0, 0, used_made={L: 5}),
                       Step(BS, 16, 20, 42, "Make G", 4, 0, 0, {S: 6, T: 4}, used_made={L: 2})],
                crafted={L: 2}, bought={S: 36, T: 4}, final_skill={BS: 20}))


class PortedSelfChecks(unittest.TestCase):
    def test_batch_size_goggles(self):
        from yap_forever.shopping import batch_size
        # Flying Tiger Goggles: 2 Tigerseye + 6 Light Leather, goggles don't stack, 16 free slots
        self.assertEqual(batch_size({818: 2, 2318: 6}, (4368, 1), {818: 20, 2318: 20, 4368: 1}, 16), 15)

    def test_route_rows_moves_intermediate_to_first_row(self):
        from yap_forever.shopping import route_rows
        rows = route_rows(chain_plan(), chain_gd())
        self.assertEqual(rows[0]["more"], 2)
        self.assertEqual(rows[0]["need"], {S: 36})
        self.assertEqual(rows[2]["need"], {S: 0, T: 4})
        self.assertEqual(rows[2]["earlier"], {L: 4})

    def test_group_trips_by_slots(self):
        from yap_forever.shopping import group_trips, route_rows
        rows = route_rows(chain_plan(), chain_gd())
        self.assertEqual([len(t) for t in group_trips(rows, 2, {S: 20, T: 20})], [2, 1])


class ShoppingListTests(unittest.TestCase):
    def test_total_is_sum_of_rounded_rows(self):
        from yap_forever.shopping import render_shopping
        gd = toy.gamedata([toy.recipe(1, "BS basic", BS, {S: 1}), toy.recipe(2, "BS basic", BS, {S: 1})])
        p = orange(Plan(steps=[Step(BS, 1, 3, 1, "BS basic", 2.2, 22, 22, {S: 2.2}),
                               Step(BS, 3, 6, 2, "BS basic", 3.1, 31, 31, {S: 3.1})],
                        bought={S: 5.3}, final_skill={BS: 6}))
        text = "\n".join(render_shopping(p, gd, toy.market({S: [(10, 100)]}), toy.stock())[0])
        self.assertIn("| Copper Bar | 7 | AH | 70c |", text)
        self.assertIn("**Gold to bring: 70c**", text)

    def test_trips_only_with_bag_slots(self):
        import dataclasses
        from yap_forever.shopping import render_shopping
        gd, p, m = chain_gd(), chain_plan(), toy.market({S: [(10, 1000)], T: [(50, 100)]})
        lines, trips = render_shopping(p, gd, m, toy.stock())
        self.assertNotIn("## Mailbox trips", lines)
        self.assertIsNone(trips)
        lines, trips = render_shopping(p, gd, m, dataclasses.replace(toy.stock(), bag_slots=60))
        self.assertIn("## Mailbox trips", lines)
        self.assertEqual(trips, 1)


def rank_trip_plan():
    p = Plan(steps=[Step(BS, 225, 235, 1, "BS one", 10, 0, 0, {S: 60}, from_stock={S: 20}),
                    Step(BS, 235, 245, 2, "BS two", 10, 0, 0, {T: 80}),
                    Step(BS, 245, 300, 3, "BS three", 55, 0, 0, {toy.ROD: 55})],
             ranks=[(BS, 225, 300, 9000)], bought={S: 40, T: 80}, vendor_bought={toy.ROD: 55},
             final_skill={BS: 300})
    orange(p)
    gd = toy.gamedata([toy.recipe(1, "BS one", BS, {S: 6}), toy.recipe(2, "BS two", BS, {T: 8}),
                       toy.recipe(3, "BS three", BS, {toy.ROD: 1})])
    for i in (S, T, toy.ROD):
        gd.items.setdefault(i, toy.item(i, "x")).stack = 20
    return p, gd


class BringListTests(unittest.TestCase):
    def trip(self):
        from yap_forever.trips import Trip
        return Trip(225, BS, "rank", "Blacksmithing rank to 300")

    def test_bring_list_fits_bags(self):
        from yap_forever.shopping import bring_list
        p, gd = rank_trip_plan()
        reach, items = bring_list(p, gd, self.trip(), bag_slots=16)  # 6 free after room for crafts
        self.assertEqual(reach, 235)
        self.assertEqual({i for i, _n, _src in items}, {S})

    def test_bring_list_without_bag_slots(self):
        from yap_forever.shopping import bring_list
        p, gd = rank_trip_plan()
        reach, items = bring_list(p, gd, self.trip(), bag_slots=None)  # rows ending within 25 points
        self.assertEqual(reach, 245)
        self.assertEqual({i for i, _n, _src in items}, {S, T})

    def test_bring_list_sources(self):
        from yap_forever.shopping import bring_list
        p, gd = rank_trip_plan()
        _reach, items = bring_list(p, gd, self.trip(), bag_slots=200)
        self.assertIn((S, 40, "mail"), items)
        self.assertIn((S, 20, "bank"), items)
        self.assertIn((toy.ROD, 55, "vendor"), items)

    def test_guide_rank_trip_bring(self):
        from yap_forever.guide import render_guide
        p, gd = rank_trip_plan()
        text = render_guide(p, gd, toy.market({S: [(10, 1000)]}), toy.stock(skills={BS: 225}), caps={BS: 300})
        line = next(l for l in text.splitlines() if l.startswith("- **Trip:**") and "rank to 300" in l)
        self.assertIn("Bring:", line)
        self.assertIn("enough to craft to 245 at the trainer", line)
        self.assertIn("no auction house, mailbox or bank", line)


if __name__ == "__main__":
    unittest.main()


class BankNeverOverdrawnTests(unittest.TestCase):
    def test_buffer_on_bank_items_is_bought(self):
        from yap_forever.shopping import render_shopping
        gd = toy.gamedata([toy.recipe(1, "BS basic", BS, {S: 1}, t=(1, 1, 300, 600))])  # yellow: buffered
        st = Step(BS, 10, 20, 1, "BS basic", 100, 0, 0, {S: 100}, from_stock={S: 100})
        p = Plan(steps=[st], final_skill={BS: 20})
        import dataclasses
        lines, _ = render_shopping(p, gd, toy.market({S: [(10, 1000)]}),
                                   dataclasses.replace(toy.stock({S: 100}), bag_slots=200))
        trip = next(l for l in lines if l.startswith("- 📬"))
        self.assertIn("From the bank: 100 Copper Bar", trip)
        self.assertIn("From the mail: 15 Copper Bar", trip)
        self.assertIn("| Copper Bar | 15 | AH |", "\n".join(lines))


class BankAcrossTripsTests(unittest.TestCase):
    def test_bank_used_once_across_trips(self):
        import dataclasses
        from yap_forever.shopping import render_shopping
        gd = toy.gamedata([toy.recipe(1, "A", BS, {S: 1}), toy.recipe(2, "B", BS, {S: 1})])
        p = orange(Plan(steps=[Step(BS, 1, 30, 1, "A", 30, 0, 0, {S: 30}, from_stock={S: 20}),
                               Step(BS, 30, 60, 2, "B", 30, 0, 0, {S: 30})],
                        bought={S: 40}, final_skill={BS: 60}))
        lines, trips = render_shopping(p, gd, toy.market({S: [(10, 1000)]}),
                                       dataclasses.replace(toy.stock({S: 20}), bag_slots=40))  # 30 a trip
        self.assertEqual(trips, 2)
        text = "\n".join(l for l in lines if l.startswith("- 📬"))
        self.assertEqual(text.count("From the bank"), 1)


class SpareBankTests(unittest.TestCase):
    def test_buffer_taken_from_spare_bank_stock(self):
        import dataclasses
        from yap_forever.shopping import render_shopping
        gd = toy.gamedata([toy.recipe(1, "BS basic", BS, {S: 1}, t=(1, 1, 300, 600))])
        p = Plan(steps=[Step(BS, 10, 20, 1, "BS basic", 100, 0, 0, {S: 100}, from_stock={S: 100})],
                 final_skill={BS: 20})
        lines, _ = render_shopping(p, gd, toy.market({S: [(10, 1000)]}),
                                   dataclasses.replace(toy.stock({S: 150}), bag_slots=200))
        trip = next(l for l in lines if l.startswith("- 📬"))
        self.assertIn("From the bank: 115 Copper Bar", trip)
        self.assertNotIn("From the mail", trip)
