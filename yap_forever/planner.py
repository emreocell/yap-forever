"""Greedy route: at each skill point, craft the recipe with the lowest net cost."""
import dataclasses
from dataclasses import dataclass, field

from yap_forever.costmodel import VENDOR_TOOLS, Cost, Pools, bars_to_ore, money, skillup_chance
from yap_forever.disenchant import DE_THRESHOLDS, de_skill_needed, de_yield
from yap_forever.gamedata import BS, ENCH, PROFESSIONS

START_CAP = 75  # Apprentice
DISENCHANT = 0  # Step.spell_id of an Enchanting skill-up from disenchanting
BUFFER = 1.15  # extra crafts on yellow and green steps, which are expected values, not promises


def buffer_factor(crafts: float) -> float:
    """1.15 for a step that may need more than one craft (yellow or green), 1 for an orange one."""
    return BUFFER if crafts > 1 + 1e-9 else 1.0


@dataclass
class Step:
    profession: int
    skill_from: int
    skill_to: int
    spell_id: int
    name: str
    crafts: float
    cash: float
    economic: float
    materials: dict[int, float] = field(default_factory=dict)  # from bank, farm, AH or vendor
    from_stock: dict[int, float] = field(default_factory=dict)  # part of materials from your bank
    used_made: dict[int, float] = field(default_factory=dict)  # your own crafts or disenchants used


@dataclass
class Plan:
    steps: list[Step] = field(default_factory=list)
    bought: dict[int, float] = field(default_factory=dict)
    vendor_bought: dict[int, float] = field(default_factory=dict)
    used_stock: dict[int, float] = field(default_factory=dict)
    farmed_bars: dict[int, float] = field(default_factory=dict)
    farm: dict[int, int] = field(default_factory=dict)  # ore -> count
    held_for_de: dict[int, tuple[float, int]] = field(default_factory=dict)
    de_materials: dict[int, float] = field(default_factory=dict)
    leftovers: dict[int, float] = field(default_factory=dict)  # produced, never used
    fees: float = 0
    favor_spent: int = 0
    skipped: list[tuple[int, str]] = field(default_factory=list)
    stalled: dict[int, int] = field(default_factory=dict)
    stall_reasons: dict[int, str] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    final_skill: dict[int, int] = field(default_factory=dict)
    learned: list[int] = field(default_factory=list)
    crafted: dict[int, float] = field(default_factory=dict)  # intermediates crafted for reagents
    cash_total: float = 0
    economic_total: float = 0
    sale_proceeds: float = 0
    leftover_value: float = 0


def apply_favor(recipes: dict, favor) -> dict:
    """Recipes listed in favor.toml are learned with Favor.

    Forever sells these as scroll items for Favor, so game data may call them "scroll"."""
    out = dict(recipes)
    for spell, price in favor.recipes.items():
        r = out.get(spell)
        if not r or r.source not in ("unknown", "scroll"):
            continue
        # Without a known skill, a placeholder orange of 1 is not trusted: use yellow.
        req = favor.skills.get(spell, r.required_skill if r.thresholds[0] > 1 else r.thresholds[1])
        out[spell] = dataclasses.replace(r, source="favor", required_skill=req)
    return out


def plan(gd, valuer, stock, favor, cap: int = 225, quests: dict | None = None,
         reuse: dict[int, tuple[float, float]] | None = None) -> Plan:
    """reuse: item -> (count later steps consume, value per unit), credited when a step makes it."""
    quests = quests or {}
    reuse = reuse or {}
    recipes = apply_favor(gd.recipes, favor)
    for spell in quests:
        if spell in recipes:
            recipes[spell] = dataclasses.replace(recipes[spell], source="quest")
    pools = Pools.from_stock(stock)
    p = Plan()
    skill = {x: max(1, stock.skills.get(x, 1)) for x in (BS, ENCH)}
    # Ranks up to the current skill are already trained; at exactly a cap the next one is not.
    rank_cap = {x: min([c for c in [START_CAP] + [r.cap for r in gd.trainer_ranks.get(x, [])]
                        if c >= skill[x]], default=START_CAP) for x in (BS, ENCH)}
    learned: set[int] = set()
    produced: dict[int, float] = {}
    held: dict[int, float] = {}
    skipped: dict[int, str] = {}
    soft_stalls: set[int] = set()  # stalled for lack of materials; retried when new ones appear
    spent = Cost()
    favor_left = stock.favor
    de_credit = 0.0  # disenchants done that have not yet added up to a skill-up
    ench_reagents = {i for r in recipes.values() if r.skill_line == ENCH for i in r.reagents}

    def tool_held(cat):
        have = set(pools.tools) | {i for i, n in pools.made.items() if n >= 1} | \
            {i for i, n in pools.stock.items() if n >= 1}
        return any(gd.satisfies(i, cat) for i in have)

    def learn_option(r):
        """(Cost, favor, scroll purchase kind, quest hand-ins) to learn r, or a reason string."""
        if r.spell_id in learned or r.source == "starter":
            return Cost(), 0, None, []
        if r.source == "trainer":
            return Cost(r.fee, r.fee), 0, None, []
        if r.source == "scroll":
            opt = valuer.buy_option(r.scroll_item, 1, pools.bought.get(r.scroll_item, 0))
            if opt is None:
                return f"scroll not available: {gd.name(r.scroll_item)}"
            return Cost(opt[1], opt[1]), 0, opt[0], []
        if r.source == "favor":
            price = favor.recipes[r.spell_id]
            return (Cost(), price, None, []) if price <= favor_left else f"not enough Favor ({price})"
        if r.source == "quest":
            if stock.level < quests[r.spell_id].level:
                return f"quest needs character level {quests[r.spell_id].level}"
            reqs = list(quests[r.spell_id].items.items())
            c = valuer.take_many(reqs, pools, skill, commit=False, learned=learned)
            if c is None:
                return "quest items not available: " + ", ".join(gd.name(i) for i, _ in reqs)
            return c, 0, None, reqs  # hand-ins are taken together with the first crafts
        return "no known source"

    def tool_option(cat):
        """Cheapest way to get a missing tool, as a dict, or None."""
        item = gd.tool_items.get(cat)
        if item is None:
            return None
        opts = []
        if item in VENDOR_TOOLS and item in gd.items:
            c = gd.items[item].buy_price
            opts.append({"how": "vendor", "item": item, "cost": Cost(c, c), "requests": [], "recipe": None})
        ah = valuer.buy_option(item, 1, pools.bought.get(item, 0))
        if ah and ah[0] == "ah":
            opts.append({"how": "ah", "item": item, "cost": Cost(ah[1], ah[1]), "requests": [], "recipe": None})
        for r in recipes.values():
            if not r.output or r.output[0] != item or skill[r.skill_line] < r.required_skill:
                continue
            if any(not tool_held(c) for c in r.tools):
                continue
            lo = learn_option(r)
            if isinstance(lo, str):
                continue
            reqs = [(i, q / r.output[1]) for i, q in r.reagents.items()]
            c = valuer.take_many(reqs, pools, skill, commit=False, learned=learned)
            if c is not None:
                opts.append({"how": "craft", "item": item, "cost": lo[0], "requests": reqs,
                             "recipe": r, "peek": c})
        if not opts:
            return None
        return min(opts, key=lambda o: o["cost"].economic + (o["peek"].score if "peek" in o else 0))

    def release_held():
        released = False
        for item in list(held):
            gate = de_skill_needed(gd.items[item].item_level)
            if skill[ENCH] >= gate:
                n = held.pop(item)
                for mat, per in de_yield(gd.items[item]).items():
                    pools.made[mat] = pools.made.get(mat, 0) + n * per
                    p.de_materials[mat] = p.de_materials.get(mat, 0) + n * per
                p.events.append(f"Enchanting {skill[ENCH]}: disenchant {n:.0f} {gd.name(item)}")
                de_skillups(n)
                released = True
        return released

    def de_skillups(n):
        """Disenchanting n items gives Enchanting skill-ups at the expected rate."""
        nonlocal de_credit
        de_credit += n
        while skill[ENCH] < min(cap, rank_cap[ENCH]):
            s = skill[ENCH]
            chance = skillup_chance(s, DE_THRESHOLDS)
            if chance <= 0:
                de_credit = 0.0
                return
            need = 1 / chance
            if de_credit + 1e-9 < need:
                return
            de_credit -= need
            last = next((x for x in reversed(p.steps) if x.profession == ENCH), None)
            if last and last.spell_id == DISENCHANT and last.skill_to == s:
                last.skill_to, last.crafts = s + 1, last.crafts + need
            else:
                p.steps.append(Step(ENCH, s, s + 1, DISENCHANT, "Disenchant greens", need, 0, 0))
            skill[ENCH] = s + 1

    def should_hold(item, opts):
        if max(opts, key=opts.get) == "de":
            return True
        info = gd.items.get(item)
        if not info or de_skill_needed(info.item_level) > cap:
            return False
        # While disenchanting still gives Enchanting skill, that beats selling the green.
        if de_yield(info) and skill[ENCH] < min(cap, DE_THRESHOLDS[3]):
            return True
        # Disenchanting is the only source of an Enchanting reagent missing from the AH.
        return any(m in ench_reagents and valuer.market.depth(m) == 0 for m in de_yield(info))

    def learn_now(r, lo, s, name):
        nonlocal favor_left, spent
        learn_cost, favor_cost, scroll_kind, _reqs = lo
        learned.add(r.spell_id)
        p.learned.append(r.spell_id)
        if r.source == "starter":
            return Cost()
        favor_left -= favor_cost
        p.favor_spent += favor_cost
        if scroll_kind:
            pool = pools.bought if scroll_kind == "ah" else pools.vendor
            pool[r.scroll_item] = pool.get(r.scroll_item, 0) + 1
        if r.source == "quest":
            q = quests[r.spell_id]
            items = ", ".join(f"{n} {gd.name(i)}" for i, n in q.items.items())
            p.events.append(f"{name} {s}: Learn {r.name} (quest from {q.giver}: hand in {items}; level {q.level})")
            return Cost()  # the hand-ins are taken and costed with the crafts
        how = {"trainer": "trainer", "scroll": "scroll", "favor": f"{favor_cost} Favor"}[r.source]
        price = f" {money(learn_cost.cash)}" if learn_cost.cash else ""
        p.events.append(f"{name} {s}: Learn {r.name} ({how}{price})")
        return learn_cost

    while True:
        active = [x for x in (BS, ENCH) if x not in p.stalled and skill[x] < cap]
        if not active:
            break
        prof = min(active, key=lambda x: (skill[x], x))
        s = skill[prof]
        name = PROFESSIONS[prof]

        if s >= rank_cap[prof]:
            nxt = next((r for r in gd.trainer_ranks.get(prof, []) if r.cap > rank_cap[prof]), None)
            if nxt is None or nxt.required_skill > s:
                p.stalled[prof], p.stall_reasons[prof] = s, f"{name}: no next rank to train at {s}"
            elif stock.level < nxt.level:
                p.stalled[prof] = s
                p.stall_reasons[prof] = f"{name}: next rank needs character level {nxt.level}"
            else:
                p.fees += nxt.fee
                spent += Cost(nxt.fee, nxt.fee)
                rank_cap[prof] = nxt.cap
                p.events.append(f"{name} {s}: train rank up to {nxt.cap} ({money(nxt.fee)})")
            continue

        best = None
        for r in recipes.values():
            if r.skill_line != prof or r.required_skill > s:
                continue
            chance = skillup_chance(s, r.thresholds)
            if chance <= 0:
                continue
            crafts = 1 / chance
            usable = max(1, min(r.thresholds[3], cap) - s)
            lo = learn_option(r)
            if isinstance(lo, str):
                skipped[r.spell_id] = lo
                continue
            tools, ok = [], True
            for cat in r.tools:
                if tool_held(cat):
                    continue
                t = tool_option(cat)
                if t is None:
                    item = gd.tool_items.get(cat)
                    skipped[r.spell_id] = f"tool not available: {gd.name(item) if item else cat}"
                    ok = False
                    break
                tools.append(t)
            if not ok:
                continue
            requests = [rq for t in tools for rq in t["requests"]] + \
                [(item, q * crafts) for item, q in r.reagents.items()]
            c = valuer.take_many(requests, pools, skill, commit=False, learned=learned)
            if c is not None and lo[3] and \
                    valuer.take_many(lo[3] + requests, pools, skill, commit=False, learned=learned) is None:
                skipped[r.spell_id] = "not enough materials for quest and reagents"
                continue
            if c is None:
                bad = next((i for i, q in requests
                            if valuer.take(i, q, pools, skill, commit=False, learned=learned) is None), None)
                skipped[r.spell_id] = (f"unpriceable: {gd.name(bad)}" if bad is not None
                                       else "not enough materials for tool and reagents")
                continue
            # Only outputs the route reuses (disenchanted for Enchanting) lower the score. Resale is
            # counted in the totals but must not pull in extra, lower-chance crafts.
            out_val = 0
            if r.output:
                de = valuer.output_options(r.output[0], produced.get(r.output[0], 0)).get("de", 0)
                out_val = de * r.output[1] * crafts
                # A reagent later steps consume is worth what it would cost, up to the count they need.
                if r.output[0] in reuse:
                    need, unit = reuse[r.output[0]]
                    left = max(0.0, need - produced.get(r.output[0], 0))
                    out_val += unit * min(r.output[1] * crafts, left)
            one_time = lo[0].economic + sum(t["cost"].economic for t in tools)
            score = c.score - out_val + one_time / usable
            key = (score, r.spell_id)
            if best is None or key < best[0]:
                best = (key, r, crafts, lo, tools, requests)

        if best is None:
            p.stalled[prof], p.stall_reasons[prof] = s, f"{name}: no usable recipe at {s}"
            soft_stalls.add(prof)
            continue

        _key, r, crafts, lo, tools, requests = best
        step_cost = Cost()
        if r.spell_id not in learned:
            requests = lo[3] + requests  # quest hand-ins, taken with the crafts
            step_cost += learn_now(r, lo, s, name)
        for t in tools:
            item = t["item"]
            if t["how"] == "craft":
                tr = t["recipe"]
                if tr.spell_id not in learned:
                    step_cost += learn_now(tr, learn_option(tr), s, PROFESSIONS[tr.skill_line])
                p.events.append(f"{name} {s}: Craft tool {gd.name(item)}")
            else:
                pool = pools.bought if t["how"] == "ah" else pools.vendor
                pool[item] = pool.get(item, 0) + 1
                step_cost += t["cost"]
                p.events.append(f"Buy tool {gd.name(item)} ({t['how']} {money(t['cost'].cash)})")
            pools.tools.add(item)
        before = _snapshot(pools)
        c = valuer.take_many(requests, pools, skill, commit=True, learned=learned)
        if c is None:  # cannot happen: same requests, same order as the check above
            p.stalled[prof], p.stall_reasons[prof] = s, f"{name}: materials ran out at {s}"
            continue
        step_cost += c
        mats, from_stock, used_made = _deltas(before, _snapshot(pools))
        made_something = False
        if r.output:
            item, per = r.output
            n = per * crafts
            opts = valuer.output_options(item, produced.get(item, 0))
            produced[item] = produced.get(item, 0) + n
            if should_hold(item, opts):
                held[item] = held.get(item, 0) + n
            else:
                pools.made[item] = pools.made.get(item, 0) + n
            made_something = True
        spent += step_cost

        last = p.steps[-1] if p.steps else None
        if last and last.profession == prof and last.spell_id == r.spell_id and last.skill_to == s:
            last.skill_to = s + 1
            last.crafts += crafts
            last.cash += step_cost.cash
            last.economic += step_cost.economic
            for mine, new in ((last.materials, mats), (last.from_stock, from_stock), (last.used_made, used_made)):
                for i, q in new.items():
                    mine[i] = mine.get(i, 0) + q
        else:
            p.steps.append(Step(prof, s, s + 1, r.spell_id, r.name, crafts, step_cost.cash, step_cost.economic,
                                mats, from_stock, used_made))
        skill[prof] = s + 1
        made_something = release_held() or made_something
        other = ENCH if prof == BS else BS
        if made_something and other in soft_stalls:
            soft_stalls.discard(other)
            p.stalled.pop(other, None)
            p.stall_reasons.pop(other, None)

    # --- wrap up -------------------------------------------------------------
    p.final_skill = dict(skill)
    p.skipped = sorted((k, v) for k, v in skipped.items() if k not in learned)
    p.crafted = dict(pools.crafted)
    p.held_for_de = {i: (n, de_skill_needed(gd.items[i].item_level)) for i, n in held.items()}
    p.bought, p.vendor_bought, p.farmed_bars = pools.bought, pools.vendor, pools.farmed
    p.farm = bars_to_ore(pools.farmed)
    p.used_stock = {i: n - pools.stock.get(i, 0) for i, n in stock.items.items()
                    if n - pools.stock.get(i, 0) > 1e-9}
    de_mats = set(p.de_materials)
    for item, n in list(pools.made.items()) + list(held.items()):
        if n < 1e-9:
            continue
        p.leftovers[item] = p.leftovers.get(item, 0) + n
        if item in de_mats:
            p.leftover_value += n * valuer.owned_value(item)
        else:
            p.sale_proceeds += sale_value(valuer, gd, item, n)
    p.cash_total = spent.cash
    p.economic_total = spent.economic - p.sale_proceeds - p.leftover_value
    return p


def _snapshot(pools) -> dict:
    return {k: dict(getattr(pools, k)) for k in ("stock", "made", "bought", "vendor", "farmed")}


def _deltas(before: dict, after: dict):
    """What one step took: (materials from outside, the bank part of them, own crafts used)."""
    def drop(k):  # amount that left pool k
        return {i: q - after[k].get(i, 0) for i, q in before[k].items() if q - after[k].get(i, 0) > 1e-9}

    def gain(k):  # amount added to pool k
        return {i: q - before[k].get(i, 0) for i, q in after[k].items() if q - before[k].get(i, 0) > 1e-9}

    from_stock = drop("stock")
    mats = dict(from_stock)
    for k in ("bought", "vendor", "farmed"):
        for i, q in gain(k).items():
            mats[i] = mats.get(i, 0) + q
    return mats, from_stock, drop("made")


def sale_value(valuer, gd, item: int, n: float) -> float:
    """Selling n crafted items: AH for the first few (all if a quest item), vendor after."""
    info = gd.items.get(item)
    vendor = info.sell_price if info else 0
    ah = valuer.market.net_sell(item) or 0
    if ah <= vendor:
        return n * vendor
    cap = min(n, valuer.sale_limit(item))
    return cap * ah + (n - cap) * vendor
