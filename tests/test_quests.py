import unittest

from tests import toy
from yap_forever.quests import QuestPlan
from tests.test_planner import BARS, base_recipes, run

BS = 164


class QuestPlanTests(unittest.TestCase):
    def test_quest_plan_learned_by_handing_in_items(self):
        # no reagents, so after the one-time hand-in it beats the copper recipe
        rs = base_recipes() + [toy.recipe(3, "Quest Belt", BS, {}, (toy.STONE, 1),
                                          source="scroll", scroll=toy.SCROLL)]
        quests = {3: QuestPlan("Quest Belt", {toy.IRON_BAR: 20}, 50, "Someone, Tanaris")}
        listings = {**BARS, toy.IRON_BAR: [(10, 1000)]}
        p = run(rs, listings, quests=quests)  # scroll itself is not on the AH
        self.assertIn(3, {s.spell_id for s in p.steps})
        self.assertAlmostEqual(p.bought[toy.IRON_BAR], 20)
        self.assertTrue(any("quest" in e and "20 Iron Bar" in e and "level 50" in e for e in p.events))
        step = next(s for s in p.steps if s.spell_id == 3)
        self.assertAlmostEqual(step.materials[toy.IRON_BAR], 20)

    def test_quest_items_unavailable_skips(self):
        rs = base_recipes() + [toy.recipe(3, "Quest Belt", BS, {}, (toy.STONE, 1),
                                          source="scroll", scroll=toy.SCROLL)]
        quests = {3: QuestPlan("Quest Belt", {toy.ODD: 1}, 50, "Someone")}
        p = run(rs, BARS, quests=quests)
        self.assertNotIn(3, {s.spell_id for s in p.steps})

    def test_real_quest_file_loads(self):
        from yap_forever.quests import load_quest_plans
        q = load_quest_plans()
        self.assertEqual(sum(sum(x.items.values()) for x in q.values()), 140)


if __name__ == "__main__":
    unittest.main()
