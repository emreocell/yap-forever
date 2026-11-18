"""The player's profile (region, ruleset, faction, characters) and their auction house."""
import json
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

STANDINGS = ("Neutral", "Friendly", "Honored", "Revered", "Exalted")
REGIONS = ("eu", "us", "kr", "tw")
FACTIONS = ("alliance", "horde")


@dataclass
class Character:
    name: str
    favor_standing: str = "Neutral"


@dataclass
class Profile:
    region: str = "eu"
    ruleset: int = 2
    faction: str = ""
    characters: dict[str, Character] = field(default_factory=dict)


def _check(key: str, value, allowed) -> None:
    if value not in allowed:
        raise ValueError(f"{key} = {value!r} in profile.toml: use one of {', '.join(map(str, allowed))}")


def load_profile(path: Path) -> Profile:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f'no {path.name} yet: run "python3 -m yap_forever init" first')
    d = tomllib.loads(path.read_text(encoding="utf-8"))
    region = d.get("region", "eu")
    faction = d.get("faction", "")
    _check("region", region, REGIONS)
    _check("faction", faction, FACTIONS)
    chars = {}
    for name, c in d.get("characters", {}).items():
        standing = c.get("favor_standing", "Neutral")
        _check(f"characters.{name}.favor_standing", standing, STANDINGS)
        chars[name] = Character(name, standing)
    return Profile(region, int(d.get("ruleset", 2)), faction, chars)


def save_house(path: Path, house: int, region: str, ruleset: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "house": house, "region": region, "ruleset": ruleset,
        "found": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")


def load_house(path: Path) -> int:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError('no auction house yet: run "python3 -m yap_forever probe" first')
    return int(json.loads(path.read_text(encoding="utf-8"))["house"])
