"""Merchant's Favor recipes and crate turn-ins."""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from yap_forever import settings


@dataclass
class Turnin:
    name: str
    items: dict[int, int]
    favor: int


@dataclass
class FavorData:
    recipes: dict[int, int]  # recipe spell -> Favor price
    skills: dict[int, int] = field(default_factory=dict)  # recipe spell -> required skill, when known
    turnins: list[Turnin] = field(default_factory=list)


def load_favor(path: Path | None = None) -> FavorData:
    path = Path(path) if path is not None else settings.paths().root / "favor.toml"
    if not path.exists():
        return FavorData({}, {}, [])
    with open(path, "rb") as f:
        d = tomllib.load(f)
    recipes, skills = {}, {}
    for r in d.get("recipe", []):
        recipes[int(r["spell_id"])] = int(r["favor"])
        if "skill" in r:
            skills[int(r["spell_id"])] = int(r["skill"])
    turnins = [Turnin(t["name"], {int(k): int(v) for k, v in t.get("items", {}).items()}, int(t["favor"]))
               for t in d.get("turnin", [])]
    return FavorData(recipes, skills, turnins)
