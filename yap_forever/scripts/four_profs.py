"""One-off: buy-everything route to 150 for LW, Tailoring, Alchemy, Engineering at today's AH prices.

Reuses the BS+Ench planner engine without editing it: professions rebound per run, disenchanting off,
empty bank, no farming, no Favor/quests. Craft vs buy is compared for intermediates.
"""
import csv, json, math, sys, tomllib, types
from pathlib import Path

from yap_forever import gamedata, planner, costmodel, config, settings
from yap_forever.prices import Market

PROFS = {165: "Leatherworking", 197: "Tailoring", 171: "Alchemy", 202: "Engineering"}
DUMMY = 999999
TARGET = 150

# disenchanting off everywhere
NEVER = lambda _il: 10**6  # noqa: E731
planner.de_skill_needed = costmodel.de_skill_needed = NEVER
planner.de_yield = costmodel.de_yield = lambda _info: {}

gamedata.PROFESSIONS = {**PROFS, DUMMY: "none"}
gd = gamedata.load_gamedata(professions=PROFS)
starters = {int(r["Spell"]) for r in csv.DictReader(open(settings.paths().gamedata / "SkillLineAbility.csv", encoding="utf-8", newline=""))
            if int(r["SkillLine"]) in PROFS and r["AcquireMethod"] == "1"}
for s, r in list(gd.recipes.items()):
    if r.source == "unknown" and s in starters:
        gd.recipes[s] = planner.dataclasses.replace(r, source="starter")

# args after the output file: 6688 = leave recipe 6688 out; +2164 = learn recipe 2164 up front,
# so intermediates it makes are crafted when that is cheaper than the AH (cost listed separately)
# @bags.toml = start from these bags ([items] id = count) and plan only `profs = [ids]` if given
BAGS = next((tomllib.load(open(x[1:], "rb")) for x in sys.argv[2:] if x.startswith("@")), {})
if BAGS.get("profs"):
    PROFS = {p: PROFS[p] for p in BAGS["profs"]}
EXCLUDE = {int(x) for x in sys.argv[2:] if x.lstrip("-").isdigit()}
PRELEARN = [int(x[1:]) for x in sys.argv[2:] if x.startswith("+")]
for s in EXCLUDE:
    gd.recipes.pop(s, None)
market = Market.load()
prelearned = []
for s in PRELEARN:
    r = gd.recipes[s]
    if r.source == "scroll":
        how, cost, item = "AH pattern", market.buy_cost(r.scroll_item, 1), r.scroll_item
    else:
        how, cost, item = "trainer", r.fee, None
    prelearned.append({"spell": s, "prof": r.skill_line, "recipe": r.name, "how": how, "cost": cost,
                       "item": str(item) if item else None, "skill": r.required_skill})
    gd.recipes[s] = planner.dataclasses.replace(r, source="starter")
# patterns already in the bags are free to learn; the planner still decides whether to use them
owned = {int(k) for k in BAGS.get("items", {})}
for s, r in list(gd.recipes.items()):
    if r.source == "scroll" and r.scroll_item in owned:
        gd.recipes[s] = planner.dataclasses.replace(r, source="starter")
stock =config.Stock(items={int(k): int(v) for k, v in BAGS.get("items", {}).items()}, favor=0, cash=0, level=60, mining=0, short_farm_ore=0, marker=None,
                     target=TARGET, mining_goal=0, quest_item_sales=5)
favor = types.SimpleNamespace(recipes={}, skills={})


class CraftOrBuy(costmodel.Valuer):
    """Like Valuer, but crafts an intermediate when that is cheaper than buying it."""

    def _take(self, item, qty, pools, skills, move, depth, learned):
        log = []

        def tmove(d, k, delta):
            d[k] = d.get(k, 0) + delta
            log.append((d, k, delta))

        def undo():
            for d, k, delta in reversed(log):
                d[k] -= delta
                if abs(d[k]) < 1e-9:
                    del d[k]
            log.clear()

        # own crafts and bank first, as in Valuer; then craft or buy the rest, whichever is cheaper
        cost, need = costmodel.Cost(), qty
        for pool, made in ((pools.made, True), (pools.stock, False)):
            n = min(pool.get(item, 0), need)
            if n > 1e-9:
                move(pool, item, -n)
                v = self.owned_value(item)
                cost = cost + costmodel.Cost(0, 0 if made else n * v, n * v)
                need -= n
        if need <= 1e-9:
            return cost
        a = super()._take(item, need, pools, skills, tmove, depth, learned)
        undo()
        b = None
        if depth < 2:
            b = self._craft(item, need, pools, skills, tmove, depth, learned)
            undo()
        if b is not None and (a is None or b.economic < a.economic - 1e-9):
            rest = self._craft(item, need, pools, skills, move, depth, learned)
        else:
            rest = super()._take(item, need, pools, skills, move, depth, learned)
        return None if rest is None else cost + rest

    def _craft(self, item, need, pools, skills, move, depth, learned):
        held = set(pools.tools) | {i for i, n in pools.made.items() if n >= 1}
        for r in self.gd.recipes.values():
            if not r.output or r.output[0] != item:
                continue
            if r.source != "starter" and r.spell_id not in learned:
                continue
            if skills.get(r.skill_line, 0) < r.required_skill:
                continue
            if any(not any(self.gd.satisfies(t, cat) for t in held) for cat in r.tools):
                continue
            crafts = need / r.output[1]
            sub = costmodel.Cost()
            for reagent, q in r.reagents.items():
                c = self._take(reagent, q * crafts, pools, skills, move, depth + 1, learned)
                if c is None:
                    return None
                sub = sub + c
            move(pools.crafted, item, need)
            return sub
        return None


valuer = CraftOrBuy(market, gd, stock)
QUALITY = {r["ID"]: int(r["OverallQualityID"] or 0) for r in csv.DictReader(open(settings.paths().gamedata / "ItemSparse.csv", encoding="utf-8", newline=""))}
out = {"snapshot": market.snapshot_time, "profs": {}, "stock": {str(k): v for k, v in stock.items.items()}}
for prof, pname in PROFS.items():
    planner.BS, planner.ENCH = prof, DUMMY
    planner.PROFESSIONS = gamedata.PROFESSIONS
    # Reagents later steps consume count as skill-ups when made as steps: replan, crediting them,
    # until the counts settle.
    makes = {r.output[0]: r for r in gd.recipes.values() if r.skill_line == prof and r.output}

    def unit_value(i):
        r = makes[i]
        craft = sum((market.min_price(j) or gd.vendor_prices.get(j) or 10**9) * q
                    for j, q in r.reagents.items()) / r.output[1]
        return min(x for x in (market.min_price(i), gd.vendor_prices.get(i), craft) if x)

    reuse = {}
    for _ in range(4):
        p = planner.plan(gd, valuer, stock, favor, cap=TARGET, quests={}, reuse=reuse)
        used = {}
        for st in p.steps:
            for i, q in gd.recipes[st.spell_id].reagents.items():
                if i in makes:
                    used[i] = used.get(i, 0) + q * st.crafts
        if reuse and all(abs(used.get(i, 0) - reuse.get(i, (0,))[0]) < 1 for i in set(used) | set(reuse)):
            break
        reuse = {i: (n, unit_value(i)) for i, n in used.items()}
    steps = []
    for st in p.steps:
        orange = all(gd.recipes[st.spell_id].thresholds[1] > x for x in range(st.skill_from, st.skill_to))
        steps.append({"from": st.skill_from, "to": st.skill_to, "spell": st.spell_id, "name": st.name,
                      "crafts": st.crafts, "orange": orange, "cash": st.cash,
                      "materials": {str(k): v for k, v in st.materials.items()},
                      # reagents this step makes on the spot, and ones it takes from earlier crafts
                      "craft_here": {str(i): c for i, q in gd.recipes[st.spell_id].reagents.items()
                                     if i in p.crafted and (c := q * st.crafts - st.materials.get(i, 0)
                                                            - st.used_made.get(i, 0)) > 0.01},
                      "from_earlier": {str(k): v for k, v in st.used_made.items() if v > 0.01},
                      "per_craft": {str(k): q for k, q in gd.recipes[st.spell_id].reagents.items()},
                      "output": [str(o[0]), o[1]] if (o := gd.recipes[st.spell_id].output) else None})
    for i, n in p.crafted.items():  # self-check: on-the-spot crafts add up to the planner's total
        assert abs(sum(x["craft_here"].get(str(i), 0) for x in steps) - n) < 0.5, (pname, gd.name(i))
    out["profs"][pname] = {
        "final": p.final_skill.get(prof), "stall": p.stall_reasons.get(prof),
        "events": [e for e in p.events], "steps": steps,
        "bought": {str(k): v for k, v in p.bought.items()},
        "vendor": {str(k): v for k, v in p.vendor_bought.items()},
        "crafted": {str(k): v for k, v in p.crafted.items()},
        "crafted_from": {str(k): next(", ".join(f"{q} {gd.name(i)}" for i, q in r.reagents.items())
                                      + (f" (makes {r.output[1]:g})" if r.output[1] != 1 else "")
                                      for r in gd.recipes.values() if r.output and r.output[0] == k)
                         for k in p.crafted},
        "leftovers": {str(k): v for k, v in p.leftovers.items()},
        # per crafted intermediate: reagents per item made, so a list can move its crafts between rows
        "made_from": {str(k): next({str(i): q / r.output[1] for i, q in r.reagents.items()}
                                   for r in gd.recipes.values() if r.output and r.output[0] == k)
                      for k in p.crafted},
        # green-or-better leftovers go to the main for disenchanting, not to a vendor
        "sale_green": sum(planner.sale_value(valuer, gd, k, n) for k, n in p.leftovers.items()
                          if QUALITY.get(str(k), 0) >= 2),
        "scrolls": [{"item": str(gd.recipes[s].scroll_item), "recipe": gd.recipes[s].name}
                    for s in p.learned if gd.recipes[s].source == "scroll"],
        "prelearned": [x for x in prelearned if x["prof"] == prof],
        "fees": p.fees, "cash": p.cash_total, "sale": p.sale_proceeds,
        "skipped_150": [(k, v, gd.recipes[k].name, gd.recipes[k].required_skill) for k, v in p.skipped
                        if k in gd.recipes and gd.recipes[k].skill_line == prof
                        and gd.recipes[k].required_skill < TARGET],
    }
    print(f"{pname}: reached {p.final_skill.get(prof)}  cash {costmodel.money(p.cash_total)}  "
          f"stall={p.stall_reasons.get(prof)}")

names = {"6219": gd.name(6219), "5956": gd.name(5956), **{str(k): gd.name(k) for k in stock.items}}
for pr in out["profs"].values():
    for d in ("bought", "vendor", "crafted", "leftovers"):
        names.update({k: gd.name(int(k)) for k in pr[d]})
    names.update({x["item"]: gd.name(int(x["item"])) for x in pr["scrolls"]})
    names.update({x["item"]: gd.name(int(x["item"])) for x in pr["prelearned"] if x["item"]})
    for st in pr["steps"]:
        names.update({k: gd.name(int(k)) for k in st["materials"]})
    for st in pr["steps"]:
        names.update({k: gd.name(int(k)) for k in st["per_craft"]})
        if st["output"]:
            names[st["output"][0]] = gd.name(int(st["output"][0]))
out["names"] = names
stackable = {r["ID"]: int(r["Stackable"] or 1) for r in csv.DictReader(open(settings.paths().gamedata / "ItemSparse.csv", encoding="utf-8", newline=""))}
out["stack"] = {k: max(1, stackable.get(k, 1)) for k in names}
out["quality"] = {k: QUALITY.get(k, 0) for k in names}
out["bag_slots"] = BAGS.get("bag_slots")  # free slots while crafting; None = not planned
out["vendor_price"] = {k: gd.vendor_prices.get(int(k)) for k in names}
out["depth"] = {k: market.depth(int(k)) for k in names}
out["min_price"] = {k: market.min_price(int(k)) for k in names}
Path(sys.argv[1]).write_text(json.dumps(out, indent=1), encoding="utf-8")
