"""Turn the planner result JSON into a shopping list (markdown)."""
import json, math, re, sys
from collections import defaultdict
from pathlib import Path

from yap_forever.prices import Market

BUFFER = 1.15  # extra on yellow/green steps (crafts are expected values)
d = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
N = d["names"]
market = Market.load()
VP = d["vendor_price"]
MONEY = re.compile(r"\((?:trainer|scroll|ah|vendor) ?((?:\d+g )?\d+s \d+c)\)|\(((?:\d+g )?\d+s \d+c)\)$")


def parse_money(s):
    g = re.search(r"(\d+)g", s)
    sv = re.search(r"(\d+)s", s)
    c = re.search(r"(\d+)c", s)
    return (int(g.group(1)) if g else 0) * 10000 + (int(sv.group(1)) if sv else 0) * 100 + (int(c.group(1)) if c else 0)


def money(c):
    c = int(round(c))
    g, s, cp = c // 10000, c // 100 % 100, c % 100
    return f"{g}g {s:02d}s {cp:02d}c" if g else (f"{s}s {cp:02d}c" if s else f"{cp}c")


def ah_cost(item, q):
    """Cost of q on the AH; if fewer are listed, the cost of all that are listed (and a flag)."""
    c = market.buy_cost(int(item), q)
    if c is not None:
        return c, False
    return market.buy_cost(int(item), market.depth(int(item))) or 0, True


def need_per_prof(p):
    need = defaultdict(float)
    for st in p["steps"]:
        k = 1.0 if st["orange"] else BUFFER
        for i, q in st["materials"].items():
            need[i] += q * k
    return {i: math.ceil(q - 1e-9) for i, q in need.items()}


def slots(counts, stack):
    return sum(math.ceil(q / stack.get(i, 1) - 1e-9) for i, q in counts.items() if q > 1e-9)


def batch_size(per_craft, output, stack, free):
    """Most crafts whose mats (from the mail) and products (until sold) fit in `free` slots at once.

    shortcut: reagents crafted on the spot and leftovers from earlier steps aren't counted; they're
    usually a stack or two."""
    best = 0
    for k in range(1, 1000):
        peak = max(slots({i: q * (k - t) for i, q in per_craft.items()}, stack)
                   + (slots({output[0]: output[1] * t}, stack) if output else 0) for t in range(k + 1))
        if peak > free:
            return best
        best = k
    return best


# self-check: Flying Tiger Goggles (2 Tigerseye + 6 Light Leather, goggles don't stack) in 16 free slots
assert batch_size({"818": 2, "2318": 6}, ["4368", 1], {"818": 20, "2318": 20, "4368": 1}, 16) == 15  # peak: mats for the last craft (2 slots) + 14 goggles


def route_rows(steps, made_from):
    """Rows with the buffer in every count; each intermediate is crafted in one go at its first row.

    shortcut: an intermediate made from another on-the-spot intermediate isn't moved; none so far."""
    rows = []
    for st in steps:
        k = 1.0 if st["orange"] else BUFFER
        rows.append({"st": st, "n": math.ceil(st["crafts"] * k - 1e-9), "more": 0.0,
                     "need": {i: q * k for i, q in st["materials"].items()},
                     "here": {i: c * k for i, c in st.get("craft_here", {}).items()},
                     "earlier": {i: c * k for i, c in st.get("from_earlier", {}).items()}})
    for i in sorted({i for r in rows for i in r["here"]}):
        first = next(r for r in rows if i in r["here"] or (r["st"].get("output") or [None])[0] == i)
        for r in rows:
            if r is first or i not in r["here"]:
                continue
            c = r["here"].pop(i)
            r["earlier"][i] = r["earlier"].get(i, 0) + c
            for j, q in made_from[i].items():
                r["need"][j] = max(0.0, r["need"].get(j, 0) - c * q)
                first["need"][j] = first["need"].get(j, 0) + c * q
            if i in first["here"]:
                first["here"][i] += c
            else:
                first["more"] += c  # the row that makes i as its own step makes these too
    return rows


def group_trips(rows, cap, stack):
    """Consecutive rows whose mats (buffered, own items included) fit in `cap` slots: one mailbox trip each."""
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
    return trips


# self-check: scraps → leather made at row 1 and again on the spot at row 3 end up all at row 1
_st = [{"orange": True, "crafts": 10, "materials": {"s": 30}, "output": ["L", 1]},
       {"orange": True, "crafts": 5, "materials": {}, "from_earlier": {"L": 5}, "output": ["K", 1]},
       {"orange": True, "crafts": 4, "materials": {"s": 6, "t": 4}, "craft_here": {"L": 2},
        "from_earlier": {"L": 2}, "output": ["G", 1]}]
_r = route_rows(_st, {"L": {"s": 3}})
assert _r[0]["more"] == 2 and _r[0]["need"] == {"s": 36} and _r[2]["need"] == {"s": 0, "t": 4} and _r[2]["earlier"] == {"L": 4}
assert [len(t) for t in group_trips(_r, 2, {"s": 20, "t": 20})] == [2, 1]  # 36 s = 2 stacks; then 1 t
CRAFT_ROOM = 10  # shortcut: slots a trip leaves for crafts and intermediates; batch notes cover rows that need more

lines = []
w = lines.append
total_need = defaultdict(int)
src_all = {}
summary = []
have = dict(d.get("stock", {}))
trip_have = dict(have)  # own items, taken off the mailbox trips in route order
used_bags = []
one_time_rows = []  # (prof, what, where, listed, cost)
w(f"# {', '.join(d['profs'])} to 150 — shopping list")
w("")
w(f"AH snapshot: {d['snapshot']}. "
  + ("What your bags hold is taken off the counts; the rest is bought, " if d.get("stock") else
     "Everything is bought: nothing from your bank, ")
  + f"no Favor recipes, no disenchanting. "
  + (f"Crafting planned for {d['bag_slots']} free bag slots (bought mats wait in the mail). " if d.get("bag_slots") else "")
  + f"Counts include a {round((BUFFER - 1) * 100)}% buffer on yellow/green steps.")
w("")
w("SUMMARY_PLACEHOLDER")
for pn, p in d["profs"].items():
    need = need_per_prof(p)
    w(f"## {pn}")
    w("")
    w("Route:")
    w("")
    rows = route_rows(p["steps"], p.get("made_from", {}))
    trips = group_trips(rows, d["bag_slots"] - CRAFT_ROOM, d["stack"]) if d.get("bag_slots") else [rows]
    # patterns bought on the AH wait in the mail: pick each up on the trip of the row that learns it
    pattern_at = {}  # id(row) -> [pattern names]
    for e in p["events"]:
        if "(scroll" in e:
            skill = int(e.split(":")[0].split()[-1])
            rec = e.split("Learn ", 1)[1].split(" (")[0]
            item = next(x["item"] for x in p["scrolls"] if x["recipe"] == rec)
            row = next((r for r in rows if r["st"]["to"] > skill), rows[-1])
            pattern_at.setdefault(id(row), []).append(N[item])
    if rows:
        pattern_at.setdefault(id(rows[0]), []).extend(N[x["item"]] for x in p.get("prelearned", []) if x["item"])
    vendor_only = {i for i in p["vendor"] if i not in p["bought"]}
    for t, trip in enumerate(trips, 1):
        if len(trips) > 1 or d.get("bag_slots"):
            tneed = defaultdict(float)
            for r in trip:
                for i, q in r["need"].items():
                    tneed[i] += q
            mail, vend, own = [], [], []
            for i, q in sorted(tneed.items(), key=lambda x: N[x[0]]):
                q = math.ceil(q - 1e-9)
                mine = min(trip_have.get(i, 0), q)
                trip_have[i] = trip_have.get(i, 0) - mine
                if mine:
                    own.append(f"{mine} {N[i]}")
                if q - mine > 0:
                    (vend if i in vendor_only else mail).append(f"{q - mine} {N[i]}")
            mail += [x for r in trip for x in pattern_at.get(id(r), [])]
            w(f"- 📬 **Trip {t}** ({slots({i: math.ceil(q) for i, q in tneed.items()}, d['stack'])} stacks of mats)."
              + (f" From the mail: {', '.join(mail)}." if mail else "")
              + (f" From the vendor: {', '.join(vend)}." if vend else "")
              + (f" Already in your bags: {', '.join(own)}." if own else ""))
        for r in trip:
            st = r["st"]
            extra = [f"first craft {math.ceil(c - 1e-9)} {N[i]} ({p['crafted_from'][i]} each)"
                     + (" — enough for later rows too" if any(i in x["earlier"] for x in rows if x is not r) else "")
                     for i, c in r["here"].items()]
            extra += [f"uses {math.ceil(c - 1e-9)} {N[i]} you made earlier" for i, c in r["earlier"].items()]
            n = r["n"]
            green = st.get("output") and d.get("quality", {}).get(st["output"][0], 0) >= 2
            if green:
                keep = math.ceil(sum(x["earlier"].get(st["output"][0], 0) for x in rows[rows.index(r) + 1:]) - 1e-9)
                extra.append(f"green: {f'keep {keep} for a later row, ' if keep else ''}"
                             f"mail {'the rest' if keep else 'them'} to your main for disenchanting")
            if d.get("bag_slots") and "per_craft" in st:
                b = batch_size(st["per_craft"], st["output"], d["stack"], d["bag_slots"])
                if b < n:
                    # a mail a player sends holds at most 12 attachments (AH mail has no such limit)
                    mails = math.ceil(slots({st["output"][0]: st["output"][1] * b}, d["stack"]) / 12) if st["output"] else 0
                    away = "mail the crafts to your main" if green else "sell or mail the crafts away"
                    extra.append(f"bags: {b} at a time (craft, then {away}: {mails} mail{'s' if mails != 1 else ''} "
                                 f"of up to 12 per batch; repeat)" if b else "bags: doesn't fit even once")
            more = math.ceil(r["more"] - 1e-9)
            w(f"- {st['from']}–{st['to']}: {st['name']} ×{n}" + (f" + {more} more for later rows" if more else "")
              + (" — " + "; ".join(extra) if extra else ""))
    w("")
    w("| Item | Count | Where | Cost |")
    w("|---|---:|---|---:|")
    mats = 0
    for i, q in sorted(need.items(), key=lambda x: N[x[0]]):
        bag = min(have.get(i, 0), q)  # bags are shared across professions, used in plan order
        have[i] = have.get(i, 0) - bag
        if bag:
            used_bags.append((pn, N[i], bag, q))
        q -= bag
        if q <= 0:
            continue
        s = "vendor" if i in p["vendor"] and i not in p["bought"] else "AH"
        src_all[i] = s if src_all.get(i, s) == s else "AH"
        total_need[i] += q
        if s == "vendor":
            c, short = VP[i] * q, False
        else:
            c, short = ah_cost(i, q)
        mats += c
        note = f" (only {market.depth(int(i))} listed)" if short else ""
        w(f"| {N[i]} | {q} | {s} | {money(c)}{note} |")
    # one-time: trainer recipes, rank, bought patterns, tools
    one = 0
    trainer = 0
    for e in p["events"]:
        m = MONEY.search(e)
        if not m:
            continue
        amt = parse_money(m.group(1) or m.group(2))
        if "(scroll" in e:
            rec = e.split("Learn ", 1)[1].split(" (")[0]
            sc = next(x for x in p["scrolls"] if x["recipe"] == rec)
            w(f"| {N[sc['item']]} | 1 | AH ({market.depth(int(sc['item']))} listed) | {money(amt)} |")
        elif e.startswith("Buy tool"):
            tool = e.replace("Buy tool ", "").split(" (")[0]
            where = "vendor" if "(vendor" in e else "AH"
            w(f"| {tool} | 1 | {where} | {money(amt)} |")
        else:
            trainer += amt
        one += amt
    for x in p.get("prelearned", []):
        if x["item"]:
            w(f"| {N[x['item']]} (to craft {x['recipe']}) | 1 | AH ({market.depth(int(x['item']))} listed) | "
              f"{money(x['cost'])} |")
        else:
            trainer += x["cost"]
        one += x["cost"]
    w(f"| Trainer: rank to 150 and recipes | | trainer | {money(trainer)} |")
    w("")
    bring = mats + one
    sale = p["sale"] - p.get("sale_green", 0)  # greens go to the main for disenchanting
    w(f"**Gold to bring: {money(bring)}.** Crafted leftovers sell back for about {money(sale)}, mostly to vendors"
      + ("; green crafts go to your main for disenchanting." if p.get("sale_green") else "."))
    w("")
    summary.append((pn, mats, one, bring, sale))

w("## All together (one order book)")
w("")
w("Buying all the lists at once walks further up the listings than each list alone.")
w("")
w("| Item | Count | Where | Unit | Listed | Cost |")
w("|---|---:|---|---:|---:|---:|")
grand = 0
for i, q in sorted(total_need.items(), key=lambda x: N[x[0]]):
    if src_all[i] == "vendor":
        c, short, unit, listed = VP[i] * q, False, VP[i], "vendor"
    else:
        c, short = ah_cost(i, q)
        unit, listed = market.min_price(int(i)), market.depth(int(i))
    grand += c
    w(f"| {N[i]} | {q} | {src_all[i]} | {money(unit)} | {listed} | {money(c)}{' (short)' if short else ''} |")
one_all = sum(s[2] for s in summary)
w("")
w(f"Materials {money(grand)} + trainer, patterns and tools {money(one_all)} = **{money(grand + one_all)}**.")

table = ["| Profession | Materials | Trainer, patterns, tools | Gold to bring | Leftovers sell for |",
         "|---|---:|---:|---:|---:|"]
for pn, mats, one, bring, sale in summary:
    table.append(f"| {pn} | {money(mats)} | {money(one)} | {money(bring)} | {money(sale)} |")
table.append(f"| **All** (shared order book) | {money(grand)} | {money(one_all)} | **{money(grand + one_all)}** | "
             f"{money(sum(s[4] for s in summary))} |")
if used_bags:
    w("")
    w("## From your bags")
    w("")
    w("| Profession | Item | Used | Needed |")
    w("|---|---|---:|---:|")
    for pn, name, bag, q in used_bags:
        w(f"| {pn} | {name} | {bag} | {q} |")
left = {N[i]: n for i, n in have.items() if n > 0}
if left:
    w("")
    w("Left in your bags: " + ", ".join(f"{n} {name}" for name, n in left.items()) + ".")
lines[lines.index("SUMMARY_PLACEHOLDER")] = "\n".join(table)
Path(sys.argv[2]).write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
