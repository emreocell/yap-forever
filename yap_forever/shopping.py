"""Shopping list, mailbox trips and what to bring to a remote trainer.

Ported from the old scripts/shopping.py, working on Plan steps. Every count includes the buffer on
yellow and green steps (planner.step_factor) and is rounded up row by row, so the total is at least
the sum of the rounded rows.
"""
import math

from yap_forever.guide import gold
from yap_forever.planner import DISENCHANT, step_factor

CRAFT_ROOM = 10  # slots a trip leaves free for crafts and intermediates
BRING_POINTS = 25  # without a bag count, bring enough for this many points (or to the stage end)


def stacks(gd, items) -> dict[int, int]:
    return {i: (gd.items[i].stack if i in gd.items else 1) for i in items}


def slots(counts: dict, stack: dict) -> int:
    return sum(math.ceil(q / stack.get(i, 1) - 1e-9) for i, q in counts.items() if q > 1e-9)


def batch_size(per_craft: dict, output, stack: dict, free: int) -> int:
    """Most crafts whose mats (from the mail) and products (until sold) fit in `free` slots at once."""
    best = 0
    for k in range(1, 1000):
        peak = max(slots({i: q * (k - t) for i, q in per_craft.items()}, stack)
                   + (slots({output[0]: output[1] * t}, stack) if output else 0) for t in range(k + 1))
        if peak > free:
            return best
        best = k
    return best


def route_rows(plan, gd) -> list[dict]:
    """Rows with the buffer in every count; each intermediate crafted on the spot is crafted in one
    go at its first row."""
    rows = []
    for st in plan.steps:
        r = gd.recipes.get(st.spell_id)
        if st.spell_id == DISENCHANT or r is None or st.skill_from >= st.skill_to:
            continue
        k = step_factor(st)
        here = {i: q * st.crafts - st.materials.get(i, 0) - st.used_made.get(i, 0)
                for i, q in r.reagents.items() if i in plan.crafted}
        rows.append({"st": st, "n": math.ceil(st.crafts * k - 1e-9), "more": 0.0,
                     "need": {i: q * k for i, q in st.materials.items()},
                     "bank": {i: q * k for i, q in st.from_stock.items()},
                     "here": {i: c * k for i, c in here.items() if c > 0.01},
                     "earlier": {i: q * k for i, q in st.used_made.items() if q > 0.01}})
    made_from = {r.output[0]: {i: q / r.output[1] for i, q in r.reagents.items()}
                 for r in gd.recipes.values() if r.output}
    for i in sorted({i for r in rows for i in r["here"]}):
        first = next(r for r in rows if i in r["here"] or (gd.recipes[r["st"].spell_id].output or (None,))[0] == i)
        for r in rows:
            if r is first or i not in r["here"]:
                continue
            c = r["here"].pop(i)
            r["earlier"][i] = r["earlier"].get(i, 0) + c
            for j, q in made_from.get(i, {}).items():
                r["need"][j] = max(0.0, r["need"].get(j, 0) - c * q)
                first["need"][j] = first["need"].get(j, 0) + c * q
            if i in first["here"]:
                first["here"][i] += c
            else:
                first["more"] += c  # the row that makes i as its own step makes these too
    return rows


def group_trips(rows, cap: int, stack: dict) -> list[list[dict]]:
    """Consecutive rows whose mats fit in `cap` slots: one mailbox trip each."""
    trips, need = [[]], {}
    for r in rows:
        trial = dict(need)
        for i, q in r["need"].items():
            trial[i] = trial.get(i, 0) + q
        if trips[-1] and slots(trial, stack) > max(cap, slots(need, stack)):  # rows adding no stacks stay
            trips.append([])
            trial = dict(r["need"])
        trips[-1].append(r)
        need = trial
    return trips if rows else []


def _bank(plan) -> dict[int, float]:
    """What the route takes from the bank: the planner's unbuffered use; the buffer on top is bought."""
    out: dict[int, float] = {}
    for st in plan.steps:
        for i, q in st.from_stock.items():
            out[i] = out.get(i, 0) + q
    return out


def _split(rows, plan, gd=None, left=None) -> dict[tuple[int, str], int]:
    """(item, source) -> count over these rows, each row rounded up; source: bank, mail (AH) or vendor.
    Farmed bars are left out (the keep list covers mining)."""
    left = _bank(plan) if left is None else left  # shared across trips, so the bank is used once
    out: dict[tuple[int, str], int] = {}
    for r in rows:
        for i, q in r["need"].items():
            if i in plan.farmed_bars:
                continue
            bank = min(q, left.get(i, 0))
            left[i] = left.get(i, 0) - bank
            vendor = i not in plan.bought and (i in plan.vendor_bought or (gd is not None and i in gd.vendor_prices))
            for src, n in (("bank", bank), ("vendor" if vendor else "mail", q - bank)):
                if n > 1e-6:
                    out[(i, src)] = out.get((i, src), 0) + math.ceil(n - 1e-6)
    return out


def bring_list(plan, gd, trip, bag_slots: int | None) -> tuple[int, list[tuple[int, int, str]]]:
    """What to bring to a remote rank trainer to keep levelling there: (skill it reaches, items)."""
    rows = [r for r in route_rows(plan, gd)
            if r["st"].profession == trip.profession and r["st"].skill_from >= trip.skill]
    if not rows:
        return trip.skill, []
    if bag_slots:
        items = {i for r in rows for i in r["need"]}
        rows = group_trips(rows, bag_slots - CRAFT_ROOM, stacks(gd, items))[0]
    else:
        later = [s for p, s, _c, _f in plan.ranks if p == trip.profession and s > trip.skill]
        limit = min([trip.skill + BRING_POINTS] + later)
        rows = [r for r in rows if r["st"].skill_to <= limit] or rows[:1]
    split = _split(rows, plan, gd)
    return rows[-1]["st"].skill_to, [(i, n, src) for (i, src), n in sorted(split.items())]


def bring_text(plan, gd, trip, bag_slots) -> str:
    reach, items = bring_list(plan, gd, trip, bag_slots)
    if not items:
        return ""
    where = {"mail": "from the mail", "bank": "from the bank", "vendor": "from a vendor"}
    parts = [f"{n} {gd.name(i)} ({where[src]})" for i, n, src in items]
    return (f" Bring: {', '.join(parts)}: enough to craft to {reach} at the trainer; the town may have "
            "no auction house, mailbox or bank, so buy and collect before you go.")


def _patterns(plan, gd, market) -> list[tuple[str, str, float]]:
    out = []
    for _p, _s, spell, how in plan.learn_log:
        r = gd.recipes.get(spell)
        if how in ("ah", "vendor") and r and r.scroll_item:
            cost = (market.min_price(r.scroll_item) or 0) if how == "ah" else gd.vendor_prices.get(r.scroll_item, 0)
            out.append((gd.name(r.scroll_item), "AH" if how == "ah" else "vendor", cost))
    return out


def render_shopping(plan, gd, market, stock) -> tuple[list[str], int | None]:
    """The '## Shopping list' section (and '## Mailbox trips' when the stock gives free bag slots);
    returns the lines and the number of mailbox trips (None without a bag count)."""
    rows = route_rows(plan, gd)
    owned = {i: float(n) for i, n in stock.items.items()}  # the buffer comes from the bank while it lasts
    split = _split(rows, plan, gd, dict(owned))
    lines = ["## Shopping list", "",
             "Counts include the buffer and are rounded up row by row, so buying them never leaves you short.", "",
             "| Item | Count | Where | Cost |", "|---|---:|---|---:|"]
    total = 0.0
    for (i, src), n in sorted(split.items(), key=lambda x: (x[0][1], gd.name(x[0][0]))):
        if src == "bank":
            continue
        cost = (gd.vendor_prices.get(i, 0) * n if src == "vendor"
                else market.buy_cost(i, n) or (market.min_price(i) or 0) * n)
        total += cost
        lines.append(f"| {gd.name(i)} | {n} | {'vendor' if src == 'vendor' else 'AH'} | {gold(cost)} |")
    for name, where, cost in _patterns(plan, gd, market):
        total += cost
        lines.append(f"| {name} | 1 | {where} | {gold(cost)} |")
    fees = plan.fees + sum(gd.recipes[s].fee for _p, _s, s, how in plan.learn_log if how == "trainer")
    if fees:
        total += fees
        lines.append(f"| Trainer: ranks and recipes | | trainer | {gold(fees)} |")
    lines += ["", f"**Gold to bring: {gold(total)}**", ""]
    if not stock.bag_slots:
        return lines, None
    stack = stacks(gd, {i for r in rows for i in r["need"]})
    trips = group_trips(rows, stock.bag_slots - CRAFT_ROOM, stack)
    lines += ["## Mailbox trips", "",
              f"Planned for {stock.bag_slots} free bag slots; bought materials wait in the mail.", ""]
    left = dict(owned)
    for t, trip in enumerate(trips, 1):
        parts = {"mail": [], "vendor": [], "bank": []}
        for (i, src), n in sorted(_split(trip, plan, gd, left).items(), key=lambda x: gd.name(x[0][0])):
            parts[src].append(f"{n} {gd.name(i)}")
        first, last = trip[0]["st"], trip[-1]["st"]
        need: dict[int, float] = {}
        for r in trip:
            for i, q in r["need"].items():
                need[i] = need.get(i, 0) + q
        lines.append(f"- 📬 **Trip {t}** (skill {first.skill_from}–{last.skill_to}, "
                     f"{slots({i: math.ceil(q - 1e-6) for i, q in need.items()}, stack)} stacks)."
                     + (f" From the mail: {', '.join(parts['mail'])}." if parts["mail"] else "")
                     + (f" From a vendor: {', '.join(parts['vendor'])}." if parts["vendor"] else "")
                     + (f" From the bank: {', '.join(parts['bank'])}." if parts["bank"] else ""))
    return lines + [""], len(trips)
