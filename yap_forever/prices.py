"""AH prices for our house: download the snapshot and answer price questions.

Usage: python3 prices.py
"""
import json
from pathlib import Path

from yap_forever import bnet
from yap_forever import settings

AH_CUT = 0.05


class Market:
    def __init__(self, listings: dict[int, list[tuple[int, int]]], snapshot_time: str = ""):
        # item -> [(unit price, quantity)] sorted cheapest first
        self.listings = {i: sorted(v) for i, v in listings.items()}
        self.snapshot_time = snapshot_time

    @classmethod
    def from_snapshot(cls, regular: dict, commodities: dict, snapshot_time: str = "") -> "Market":
        out: dict[int, list[tuple[int, int]]] = {}
        for a in (regular or {}).get("auctions", []):
            if "buyout" not in a:
                continue  # bid-only listing
            # Forever regular listings are always quantity 1, so buyout is the unit price.
            out.setdefault(a["item"]["id"], []).append((a["buyout"], a.get("quantity", 1)))
        for a in (commodities or {}).get("auctions", []):
            out.setdefault(a["item"]["id"], []).append((a["unit_price"], a["quantity"]))
        return cls(out, snapshot_time)

    def buy_cost(self, item_id: int, qty: int) -> int | None:
        """Cost of buying qty units cheapest-first; None if not enough listed."""
        if qty <= 0:
            return 0
        total, need = 0, qty
        for price, n in self.listings.get(item_id, []):
            take = min(n, need)
            total += take * price
            need -= take
            if need == 0:
                return total
        return None

    def min_price(self, item_id: int) -> int | None:
        lst = self.listings.get(item_id)
        return lst[0][0] if lst else None

    def net_sell(self, item_id: int) -> int | None:
        p = self.min_price(item_id)
        return None if p is None else int(p * (1 - AH_CUT))

    def depth(self, item_id: int) -> int:
        return sum(n for _, n in self.listings.get(item_id, []))

    def save(self, path: Path | None = None) -> None:
        path = Path(path) if path is not None else settings.paths().prices
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"snapshot_time": self.snapshot_time,
                "listings": {str(i): v for i, v in self.listings.items()}}
        path.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> "Market":
        path = Path(path) if path is not None else settings.paths().prices
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls({int(i): [tuple(x) for x in v] for i, v in d["listings"].items()},
                   d.get("snapshot_time", ""))


def fetch(client, house: int, ruleset: int, prices_path: Path, log_path: Path) -> int:
    """Download the house's snapshot unless it is unchanged. Returns an exit code."""
    since = Market.load(prices_path).snapshot_time or None if prices_path.exists() else None
    try:
        r = client.get(bnet.house_path(house, ruleset), if_modified_since=since)
        if r.status == 304:
            print(f"No new snapshot since {since}.")
            return 0
        comm = client.get(bnet.house_path(house, ruleset, commodities=True)).body or {}
    except bnet.AuthError:
        print(bnet.AUTH_MESSAGE)
        return 2
    except bnet.ApiError as e:
        print(e if e.status == 0 else f"{e} — the Forever API route may have changed.")
        return 1
    m = Market.from_snapshot(r.body or {}, comm, r.last_modified or "")
    m.save(prices_path)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{r.last_modified}\n")
    print(f"Saved {len(m.listings)} items from house {house}, snapshot {r.last_modified}.")
    return 0


