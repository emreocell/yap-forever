"""A readable levelling guide: what to keep while levelling, the route in skill ranges, money."""
import math
import re
import tomllib

from yap_forever.config import STATIC_DIR
from yap_forever.costmodel import BARS, ORES, STONES
from yap_forever.gamedata import BS, ENCH, PROFESSIONS

with open(STATIC_DIR / "sources.toml", "rb") as _f:
    SOURCES = {group: {int(k): v for k, v in items.items()} for group, items in tomllib.load(_f).items()}
with open(STATIC_DIR / "disenchant.toml", "rb") as _f:
    DE_MATS = {m[0] for band in tomllib.load(_f)["band"]
               for m in (band.get("dust"), band.get("essence"), band.get("shard")) if m}

GROUPS = ["Mining", "Skinning", "Cloth", "Enchanting materials", "Drops and AH"]
EVENT = re.compile(r"^(Blacksmithing|Enchanting) (\d+): (.*)$")
DISENCHANT = re.compile(r"^disenchant ([\d.]+) (.*)$")
UNNAMED = re.compile(r"\bspell (\d+)\b")


def recipe_name(spell: int, name: str, gd) -> str:
    """Some recipes have no name in the client data; show the item they make instead."""
    r = gd.recipes.get(spell)
    if UNNAMED.fullmatch(name) and r and r.output:
        return gd.name(r.output[0])
    return name


def _fix_names(text: str, gd) -> str:
    return UNNAMED.sub(lambda m: recipe_name(int(m.group(1)), m.group(0), gd), text)


def source_group(item: int, gd) -> str:
    """How you get an item: Mining, Skinning, Cloth, Enchanting materials, Vendor, or Drops and AH."""
    if item in ORES or item in BARS or item in STONES or item in SOURCES["mining"] or _stone_made(item, gd):
        return "Mining"
    if item in SOURCES["skinning"]:
        return "Skinning"
    if item in SOURCES["cloth"]:
        return "Cloth"
    if item in DE_MATS:
        return "Enchanting materials"
    if item in gd.vendor_prices:
        return "Vendor"
    return "Drops and AH"


def _stone_made(item: int, gd):
    """(stone, count) if item is a grinding or sharpening stone made from one kind of stone."""
    for r in gd.recipes.values():
        if r.output and r.output[0] == item and len(r.reagents) == 1:
            (stone, q), = r.reagents.items()
            if stone in STONES:
                return stone, q / r.output[1]
    return None


def count(q: float) -> str:
    return f"{math.ceil(q - 1e-6):,}"


def gold(copper: float) -> str:
    c = int(round(copper))
    if c >= 100000:
        return f"{c / 10000:,.0f}g"
    if c >= 10000:
        return f"{c / 10000:.1f}g"
    if c >= 100:
        return f"{c // 100}s"
    return f"{c}c"


def _add(into: dict, more: dict) -> None:
    for i, q in more.items():
        into[i] = into.get(i, 0) + q


def render_guide(plan, gd, market, stock) -> str:
    target = stock.target
    out = [f"# Blacksmithing + Enchanting to {target}", "",
           "Level both professions side by side: craft in whichever one is lower. "
           "Until you switch, gather and keep the materials below instead of selling them.", ""]
    _keep(out, plan, gd, market)
    _route(out, plan, gd, target, stock.quest_item_sales)
    _money(out, plan, stock)
    _notes(out, plan, market)
    return "\n".join(out) + "\n"


# --- keep while levelling ------------------------------------------------------
def _keep(out, plan, gd, market) -> None:
    need, bank = {}, {}
    for s in plan.steps:
        _add(need, s.materials)
        _add(bank, s.from_stock)
    groups: dict[str, list] = {}
    for item, q in need.items():
        groups.setdefault(source_group(item, gd), []).append(item)

    out += ["## Keep while levelling", "",
            "Counts are for the whole route. *Buy later* is what the part you still need would cost "
            "on your AH today, so the top rows are the ones most worth keeping.", ""]
    for group in GROUPS:
        items = groups.get(group)
        if not items:
            continue
        rows = []
        for item in items:
            still = max(0.0, need[item] - bank.get(item, 0))
            rows.append((_buy_later(item, still, market), item, still))
        rows.sort(key=lambda r: -r[0][0])
        out += [f"### {group}", "", "| Item | Keep | In bank | Still to get | Buy later |",
                "|---|---|---|---|---|"]
        for (_, price), item, still in rows:
            out.append(f"| {_label(item, gd)} | {count(need[item])} | {count(bank.get(item, 0))} "
                       f"| {count(still)} | {price} |")
        out.append("")
        out += _group_notes(group, items, gd)

    vendor = groups.get("Vendor", [])
    if vendor:
        total = sum(need[i] * gd.vendor_prices.get(i, 0) for i in vendor)
        listed = ", ".join(f"{count(need[i])} {gd.name(i)}" for i in sorted(vendor, key=lambda i: -need[i]))
        out += ["### Buy from a vendor when you switch", "",
                f"No need to stockpile: {listed}. About {gold(total)} in total.", ""]


def _buy_later(item, still, market) -> tuple[float, str]:
    if still < 1e-6:
        return 0, "—"
    cost = market.buy_cost(item, math.ceil(still - 1e-6))
    if cost is not None:
        return cost, gold(cost)
    low = market.min_price(item)
    if low is None:
        return 0, "not on AH"
    return low * still, f"{gold(low * still)} (only {market.depth(item)} listed)"


def _label(item, gd) -> str:
    made = _stone_made(item, gd)
    if made:
        stone, q = made
        return f"{gd.name(item)} (or {q:g} {gd.name(stone)} each)"
    return gd.name(item)


def _group_notes(group, items, gd) -> list[str]:
    notes = []
    if group == "Mining":
        bars = [i for i in items if i in BARS]
        if bars:
            notes.append("Bars: mine the ore and smelt it. Bronze = Copper + Tin; "
                         "Steel = Iron + Coal (Coal from a vendor).")
        unused = [n for i, n in SOURCES["mining"].items() if i not in items]
    elif group == "Skinning":
        unused = [n for i, n in SOURCES["skinning"].items() if i not in items]
    elif group == "Enchanting materials":
        notes.append("Disenchanting your own Blacksmithing greens already covers part of Enchanting; "
                     "these are the extra materials on top.")
        unused = []
    else:
        unused = []
    if unused:
        notes.append("Safe to sell, the route doesn't use them: " + ", ".join(unused) + ".")
    return notes + ([""] if notes else [])


# --- route ---------------------------------------------------------------------
def _route(out, plan, gd, target, quest_limit) -> None:
    used_by: dict[int, list[str]] = {}
    for s in plan.steps:
        for item in s.used_made:
            name = recipe_name(s.spell_id, s.name, gd)
            if name not in used_by.setdefault(item, []):
                used_by[item].append(name)
    disenchanted = {m.group(3) for e in plan.events if (m := EVENT.match(e))}
    disenchanted = {t.split(" ", 2)[2] for t in disenchanted if t.startswith("disenchant ")}
    held = {gd.name(i) for i in plan.held_for_de}

    lines: dict[int, list] = {BS: [], ENCH: []}  # profession -> [(skill, order, text)]
    for prof in (BS, ENCH):
        for r in _ranges([s for s in plan.steps if s.profession == prof], gd):
            lines[prof].append((r["from"], 1, _range_line(r, gd, used_by, disenchanted | held, quest_limit)))
    de: dict[str, list] = {}  # item name -> [first skill, last skill, count]
    for e in plan.events:
        m = EVENT.match(e)
        if not m:
            continue
        prof, at, text = (BS if m.group(1) == "Blacksmithing" else ENCH), int(m.group(2)), m.group(3)
        d = DISENCHANT.match(text)
        if d:
            first, last, n = de.get(d.group(2), [at, at, 0])
            de[d.group(2)] = [first, at, n + float(d.group(1))]
            continue
        lines[prof].append((at, 0, f"- *At {at}: {_fix_names(text, gd)}*"))
    for item, (first, last, n) in de.items():
        text = (f"- *At {first}: disenchant {count(n)} {item}*" if first == last else
                f"- *From {first}: disenchant your {item} as you make them ({count(n)} in all, by {last})*")
        lines[ENCH].append((first, 2, text))

    out += ["## Route", ""]
    for lo, hi in ((1, 150), (150, 225), (225, target)):
        if lo >= hi:
            continue
        block: list[str] = []
        for prof in (BS, ENCH):
            part = sorted(x for x in lines[prof] if lo <= x[0] < hi or (hi == target and x[0] == hi))
            if part:
                block += [f"**{PROFESSIONS[prof]}**", ""] + [t for _, _, t in part] + [""]
        if block:
            out += [f"### Skill {lo}–{hi}", ""] + block


def _ranges(steps, gd) -> list[dict]:
    out: list[dict] = []
    for s in steps:
        last = out[-1] if out else None
        if last and last["spell"] == s.spell_id and last["to"] == s.skill_from:
            last["to"] = s.skill_to
            last["crafts"] += s.crafts
            _add(last["mats"], s.materials)
            _add(last["own"], s.used_made)
        else:
            out.append({"spell": s.spell_id, "name": recipe_name(s.spell_id, s.name, gd), "from": s.skill_from, "to": s.skill_to,
                        "crafts": s.crafts, "mats": dict(s.materials), "own": dict(s.used_made)})
    return out


def _range_line(r, gd, used_by, for_de, quest_limit=None) -> str:
    n = max(1, round(r["crafts"]))
    mats = [f"{count(q)} {gd.name(i)}" for i, q in r["mats"].items()] + \
           [f"{count(q)} {gd.name(i)} (yours)" for i, q in r["own"].items()]
    line = f"- **{r['from']}–{r['to']}** · {n}× {r['name']}"
    if mats:
        line += " — " + ", ".join(mats)
    recipe = gd.recipes.get(r["spell"])
    if recipe and recipe.output:
        item = recipe.output[0]
        if item in used_by:
            line += f" → keep for {', '.join(used_by[item])}"
        elif gd.name(item) in for_de:
            line += " → keep for disenchanting"
        elif item in gd.quest_items and quest_limit is not None:
            line += f" → sell up to {quest_limit} on the AH (quest item), the rest to a vendor"
        elif item in gd.quest_items:
            line += " → sell on the AH (quest item, steady demand)"
        else:
            line += " → sell (up to 5 on the AH, the rest to a vendor)"
    return line


# --- money and notes -------------------------------------------------------------
def _money(out, plan, stock) -> None:
    out += ["## Money", "",
            f"- **Spent along the way:** about {gold(plan.cash_total)}, including {gold(plan.fees)} of "
            "trainer ranks. It is spread over the whole route, and sales come in as you go.",
            f"- **Back from selling crafts:** about {gold(plan.sale_proceeds)}.",
            f"- **Net:** about {gold(abs(plan.economic_total))} "
            f"{'cost' if plan.economic_total > 0 else 'profit'}, counting your bank and mined bars "
            "at what they would sell for.",
            f"- **Merchant's Favor:** {plan.favor_spent} of {stock.favor} spent.", ""]


def _notes(out, plan, market) -> None:
    out += ["## Notes", ""]
    for reason in plan.stall_reasons.values():
        out.append(f"- Stops early: {reason}.")
    if any("quest from" in e for e in plan.events):
        out.append("- Imperial Plate plans come from quests that need character level 50; "
                   "bring the Thorium Bars shown in the route.")
    out += ["- Leather is costed as bought on the AH; since you skin, gather it instead.",
            "- Stones are counted as mined along with the ore.",
            f"- Prices: your AH snapshot of {market.snapshot_time or 'unknown time'}.", ""]
