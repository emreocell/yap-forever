"""The least-gold and least-total-value routes side by side, with what each asks of your time."""
import math

from yap_forever.gamedata import PROFESSIONS
from yap_forever.guide import gold
from yap_forever.trips import trips

ROUTE_NAMES = {"gold": "Least gold", "value": "Least total value"}
THIN_SHARE = 0.5  # buying at least half of what is listed moves the price


def _to_sell(plan, gd, market) -> str:
    items = {i: n for i, n in plan.leftovers.items() if n >= 1 and market.net_sell(i) and i not in plan.held_for_de}
    if not items:
        return "nothing"
    count = sum(math.floor(n) for n in items.values())
    listings = sum(math.ceil(math.floor(n) / (gd.items[i].stack if i in gd.items else 1)) for i, n in items.items())
    return f"{count} items in {listings} listings"


def _thin(plan, gd, market) -> str:
    names = []
    for i, n in sorted(plan.bought.items()):
        depth = market.depth(i)
        if depth and n >= THIN_SHARE * depth:
            names.append(f"{gd.name(i)} (buys {math.ceil(n)} of {depth})")
    for i, n in sorted(plan.leftovers.items()):
        depth = market.depth(i)
        if market.net_sell(i) and i not in plan.held_for_de and n > depth:
            names.append(f"{gd.name(i)} (sells {math.floor(n)}, {depth} listed)")
    return "; ".join(names) or "none"


def settle_routes(routes: dict) -> tuple[dict, bool]:
    """The planner chooses one skill point at a time, so its least-gold route can end up spending more
    gold than the least-total-value one. Then the latter is the least-gold route too."""
    g, v = routes.get("gold"), routes.get("value")
    if g is not None and v is not None and v.cash_total <= g.cash_total + 1e-9:
        return {**routes, "gold": v}, True
    return routes, False


def compare(routes: dict, gd, market, stock, mailbox_trips: dict | None = None, same: bool = False) -> str:
    modes = [m for m in ROUTE_NAMES if m in routes]

    def row(label, f):
        return f"| {label} | " + " | ".join(f(routes[m], m) for m in modes) + " |"

    reached = lambda p, _m: ", ".join(f"{PROFESSIONS.get(x, x)} {s}" for x, s in p.final_skill.items()) or "—"
    away = lambda p, _m: str(len(trips(p, gd))) if trips(p, gd) else "none"
    mail = lambda _p, m: str(mailbox_trips[m]) if mailbox_trips and m in mailbox_trips else "—"
    return "\n".join([
        "| | " + " | ".join(ROUTE_NAMES[m] for m in modes) + " |",
        "|---|" + "---:|" * len(modes),
        row("Gold out of pocket", lambda p, _m: gold(p.cash_total)),
        row("Total value", lambda p, _m: gold(p.economic_total)),
        row("Reached", reached),
        row("To sell", lambda p, _m: _to_sell(p, gd, market)),
        row("Mailbox trips", mail),
        row("Trips away", away),
        row("Thin markets", lambda p, _m: _thin(p, gd, market)),
    ] + (["", "The least-total-value route also spends the least gold, so both guides are the same route."]
         if same else []))
