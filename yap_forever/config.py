"""Paths, credentials and the user's stock file."""
import json
import os
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
STATIC_DIR = APP_DIR / "data_static"
USER_DIR = Path.home() / ".yap-forever"
CONFIG_PATH = APP_DIR / "config.json"


@dataclass(frozen=True)
class Credentials:
    client_id: str = field(repr=False)
    client_secret: str = field(repr=False)
    region: str = "eu"

    def __repr__(self):
        return f"Credentials(region={self.region!r}, client_id=***, client_secret=***)"

    __str__ = __repr__


def load_credentials(path: Path = CONFIG_PATH) -> Credentials:
    path = Path(path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise PermissionError(f"{path.name} must be readable only by you: run chmod 600 on it")
    data = json.loads(path.read_text())
    cid, secret = data.get("client_id", ""), data.get("client_secret", "")
    if not cid or not secret:
        raise ValueError("fill in client_id and client_secret in config.json")
    return Credentials(cid, secret, data.get("region", "eu"))


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


def load_stock(path: Path = USER_DIR / "stock.toml") -> Stock:
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
