"""Credentials type, static data folder and the stock file."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent / "data_static"


@dataclass(frozen=True)
class Credentials:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    region: str = "eu"

    def __repr__(self):
        return f"Credentials(region={self.region!r}, client_id=***, client_secret=***)"

    __str__ = __repr__


@dataclass
class Stock:
    items: dict[int, int]
    favor: int
    cash: int  # copper, soft budget
    level: int
    mining: int
    short_farm_ore: int
    marker: tuple[int, int] | None
    target: int = 225  # skill both professions are planned to
    mining_goal: int = 0  # Mining skill you'll reach while farming; 0 = current
    quest_item_sales: int | None = None  # quest items you expect to sell on the AH; None = no limit


def load_stock(path: Path) -> Stock:
    with open(path, "rb") as f:
        d = tomllib.load(f)
    m = d.get("marker", {})
    marker = None
    if m.get("item_id") and m.get("buyout_copper"):
        marker = (int(m["item_id"]), int(m["buyout_copper"]))
    return Stock(
        items={int(k): int(v) for k, v in d.get("items", {}).items()},
        favor=int(d.get("favor", 0)),
        cash=int(round(float(d.get("cash_gold", 0)) * 10000)),
        level=int(d.get("level", 1)),
        mining=int(d.get("mining", 0)),
        short_farm_ore=int(d.get("short_farm_ore", 200)),
        marker=marker,
        target=int(d.get("target", 225)),
        mining_goal=int(d.get("mining_goal", d.get("mining", 0))),
        quest_item_sales=int(d["quest_item_sales"]) if "quest_item_sales" in d else None,
    )
