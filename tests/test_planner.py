import unittest

from tests import toy
from yap_forever.costmodel import Valuer
from yap_forever.favor import FavorData
from yap_forever.planner import plan

BS, ENCH = 164, 333


def base_recipes():
    """One cheap always-orange recipe per profession."""
    return [
        toy.recipe(1, "BS basic", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1)),
        toy.recipe(2, "Ench basic", ENCH, {toy.ROD: 1}),
    ]


def run(recipes, listings=None, stock=None, favor=toy.NO_FAVOR, quest=(), cap=225, quests=None, reuse=None):
    gd = toy.gamedata(recipes, quest_items=quest)
    st = stock or toy.stock()
    return plan(gd, Valuer(toy.market(listings), gd, st), st, favor, cap=cap, quests=quests, reuse=reuse)


BARS = {toy.COPPER_BAR: [(100, 100000)]}


class PlannerTests(unittest.TestCase):
    def test_reaches_cap_both(self):
        p = run(base_recipes(), BARS)
        self.assertEqual(p.final_skill, {BS: 225, ENCH: 225})
        self.assertEqual(p.stalled, {})

    def test_picks_cheapest_per_point(self):
        rs = base_recipes() + [toy.recipe(3, "BS iron", BS, {toy.IRON_BAR: 1}, (toy.STONE, 1))]
        p = run(rs, {**BARS, toy.IRON_BAR: [(10, 100000)]})
        self.assertEqual({s.spell_id for s in p.steps if s.profession == BS}, {3})

    def test_reuse_credit_picks_needed_reagent_up_to_count(self):
        rs = base_recipes() + [toy.recipe(3, "BS iron", BS, {toy.IRON_BAR: 1}, (toy.VEST, 1))]
        p = run(rs, {**BARS, toy.IRON_BAR: [(90, 100000)]}, reuse={toy.STONE: (10, 50)})
        basic = [s for s in p.steps if s.profession == BS and s.spell_id == 1]
        self.assertEqual(sum(s.crafts for s in basic), 10)  # 100 - 50 beats 90, but only for 10 stones
        self.assertEqual(basic[0].skill_from, 1)

    def test_skips_unpriceable_with_reason(self):
        rs = base_recipes() + [toy.recipe(3, "BS odd", BS, {toy.ODD: 1}, (toy.STONE, 1))]
        p = run(rs, BARS)
        self.assertIn((3, f"unpriceable: Odd Thing"), p.skipped)

    def test_not_planned_below_required_skill(self):
        rs = base_recipes() + [toy.recipe(3, "BS iron", BS, {toy.IRON_BAR: 1}, (toy.STONE, 1), req=30)]
        p = run(rs, {**BARS, toy.IRON_BAR: [(10, 100000)]})
        first_iron = min(s.skill_from for s in p.steps if s.spell_id == 3)
        self.assertEqual(first_iron, 30)

    def test_plan_starts_from_stock_skills(self):
        p = run(base_recipes(), BARS, stock=toy.stock(skills={BS: 100, ENCH: 120}))
        self.assertEqual(min(s.skill_from for s in p.steps if s.profession == BS), 100)
        self.assertEqual(min(s.skill_from for s in p.steps if s.profession == ENCH), 120)
        self.assertEqual(p.fees, 4500 + 5000)  # the 150 ranks are already trained

    def test_skill_at_rank_cap_trains_next_rank(self):
        p = run(base_recipes(), BARS, stock=toy.stock(skills={BS: 150, ENCH: 150}))
        self.assertEqual(p.fees, 4500 + 5000)
        self.assertEqual(p.final_skill, {BS: 225, ENCH: 225})

    def test_rank_fee_added_at_cap(self):
        p = run(base_recipes(), BARS)
        self.assertEqual(p.fees, 450 + 4500 + 500 + 5000)

    def test_level_too_low_stalls(self):
        p = run(base_recipes(), BARS, stock=toy.stock(level=15))
        self.assertEqual(p.stalled, {BS: 150, ENCH: 150})
        self.assertTrue(any("level 20" in r for _, r in p.stall_reasons.items()))

    def test_stalls_without_candidates(self):
        rs = [toy.recipe(1, "BS short", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1), t=(1, 40, 50, 60)),
              toy.recipe(2, "Ench basic", ENCH, {toy.ROD: 1})]
        p = run(rs, BARS)
        self.assertEqual(p.stalled, {BS: 60})
        self.assertEqual(p.final_skill[ENCH], 225)

    def test_greens_disenchanted_as_made(self):
        rs = [toy.recipe(1, "Belt", BS, {toy.COPPER_BAR: 1}, (toy.BELT, 1)),
              toy.recipe(2, "Ench dust", ENCH, {toy.DUST: 1})]
        p = run(rs, {**BARS, toy.DUST: [(300, 100000)]}, cap=40)
        # Forever has no item-level gate: belts (ilvl 22) are disenchanted from Enchanting 1
        self.assertEqual(p.held_for_de, {})
        self.assertTrue(any(e.startswith("Enchanting 1: disenchant") for e in p.events))
        self.assertGreater(p.de_materials.get(toy.DUST, 0), 0)

    def test_disenchants_raise_enchanting(self):
        rs = [toy.recipe(1, "Belt", BS, {toy.COPPER_BAR: 1}, (toy.BELT, 1)),
              toy.recipe(2, "Ench dust", ENCH, {toy.DUST: 1})]
        p = run(rs, {**BARS, toy.DUST: [(300, 100000)]}, cap=40)
        de_steps = [s for s in p.steps if s.profession == ENCH and s.spell_id == 0]
        self.assertTrue(de_steps)
        self.assertEqual(de_steps[0].skill_from, 1)
        self.assertEqual(sum(s.cash + s.economic for s in de_steps), 0)
        # Enchanting steps, recipes and disenchants together, cover every point without gaps.
        ench = sorted((s.skill_from, s.skill_to) for s in p.steps if s.profession == ENCH)
        self.assertEqual(ench[0][0], 1)
        for (_, a), (b, _) in zip(ench, ench[1:]):
            self.assertEqual(a, b)
        self.assertEqual(ench[-1][1], p.final_skill[ENCH])

    def test_disenchant_skillups_stop_at_60(self):
        rs = [toy.recipe(1, "Belts", BS, {toy.COPPER_BAR: 1}, (toy.BELT, 5))]
        p = run(rs, BARS, cap=75)
        self.assertEqual(p.final_skill[ENCH], 60)
        crafts = sum(s.crafts for s in p.steps if s.profession == ENCH and s.spell_id == 0)
        self.assertAlmostEqual(crafts, 190.1, delta=0.5)

    def test_favor_limit_respected(self):
        rs = base_recipes() + [
            toy.recipe(3, "Fav A", BS, {}, (toy.STONE, 1), source="unknown"),
            toy.recipe(4, "Fav B", ENCH, {}, None, source="unknown")]
        fav = FavorData({3: 30, 4: 30}, {3: 1, 4: 1}, [])
        p = run(rs, BARS, stock=toy.stock(favor=30), favor=fav)
        self.assertEqual(p.favor_spent, 30)
        learned = {s.spell_id for s in p.steps} & {3, 4}
        self.assertEqual(len(learned), 1)

    def test_scroll_recipe_priced_or_skipped(self):
        rs = base_recipes() + [toy.recipe(3, "Scroll free", BS, {}, (toy.STONE, 1),
                                          source="scroll", scroll=toy.SCROLL)]
        p = run(rs, BARS)  # scroll not on AH, not vendor-sold
        self.assertIn((3, "scroll not available: Plans: Something"), p.skipped)
        p2 = run(rs, {**BARS, toy.SCROLL: [(500, 1)]})
        self.assertIn(3, {s.spell_id for s in p2.steps})
        self.assertIn("Learn Scroll free (scroll 5s 0c)", " ".join(p2.events))

    def test_missing_rod_adds_tool_cost_once(self):
        rs = [toy.recipe(1, "BS basic", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1)),
              toy.recipe(2, "Ench rod-needing", ENCH, {toy.ROD: 1}, tools=[373]),
              toy.recipe(5, "Runed Copper Rod", ENCH, {toy.ROD: 1}, (toy.ROD_TOOL, 1), source="starter")]
        p = run(rs, BARS)
        tool_events = [e for e in p.events if "tool" in e.lower()]
        self.assertLessEqual(len(tool_events), 1)
        self.assertEqual(p.final_skill[ENCH], 225)

    def test_hammer_bought_from_vendor(self):
        rs = [toy.recipe(1, "BS hammer", BS, {toy.COPPER_BAR: 1}, (toy.STONE, 1), tools=[162]),
              toy.recipe(2, "Ench basic", ENCH, {toy.ROD: 1})]
        p = run(rs, BARS)
        self.assertEqual(p.final_skill[BS], 225)
        self.assertIn("Buy tool Blacksmith Hammer (vendor 0s 18c)", p.events)

    def test_stock_used_and_totals(self):
        p = run(base_recipes(), BARS, stock=toy.stock({toy.COPPER_BAR: 10}))
        self.assertEqual(p.used_stock.get(toy.COPPER_BAR), 10)
        self.assertGreater(p.cash_total, 0)
        self.assertGreaterEqual(p.economic_total, p.cash_total - p.sale_proceeds - p.leftover_value)


if __name__ == "__main__":
    unittest.main()


class FavorScrollTests(unittest.TestCase):
    def test_favor_listing_overrides_scroll_source(self):
        # Forever Favor recipes are taught by a scroll item sold for Favor, so game data says "scroll".
        rs = base_recipes() + [toy.recipe(3, "Fav scroll", BS, {}, (toy.STONE, 1),
                                          source="scroll", scroll=toy.SCROLL)]
        fav = FavorData({3: 30}, {3: 1}, [])
        p = run(rs, BARS, stock=toy.stock(favor=30), favor=fav)
        self.assertEqual(p.favor_spent, 30)
        self.assertIn(3, {s.spell_id for s in p.steps})
        self.assertNotIn(3, {sid for sid, _ in p.skipped})


class NoOvercraftTests(unittest.TestCase):
    def test_resale_does_not_pick_lower_chance_recipe(self):
        # orange: 1 Copper Bar per point. "Vest" goes yellow at once, so it needs more crafts per
        # point, but each Vest resells for far more than its bar. Levelling should not chase resale.
        rs = base_recipes() + [toy.recipe(3, "Vest", BS, {toy.COPPER_BAR: 1}, (toy.VEST, 1), t=(1, 1, 50, 99))]
        p = run(rs, {**BARS, toy.VEST: [(1000, 50)]}, cap=40)
        self.assertNotIn(3, {s.spell_id for s in p.steps})
