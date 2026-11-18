"""Move a personal planner folder (the layout before yap-forever) into the home layout.

Never touches credentials: the player copies those themselves.
"""
import json
import shutil
import tomllib
from pathlib import Path

from yap_forever import profile
from yap_forever.settings import Paths


def _copy(src: Path, dst: Path, actions: list[str]) -> None:
    if not src.exists():
        actions.append(f"skipped {src} (not found)")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    actions.append(f"copied {src} -> {dst}")


def _add_goals(stock: Path, actions: list[str]) -> None:
    """Older stock files plan Blacksmithing + Enchanting to `target`; say so in a [goals] table."""
    if not stock.exists():
        return
    text = stock.read_text(encoding="utf-8")
    d = tomllib.loads(text)
    if "goals" in d:
        return
    target = int(d.get("target", 225))
    sep = "" if text.endswith("\n") else "\n"
    stock.write_text(f"{text}{sep}\n[goals]\nblacksmithing = {target}\nenchanting = {target}\n",
                     encoding="utf-8")
    actions.append(f"added [goals] (Blacksmithing and Enchanting to {target}) to {stock}")


def migrate(user_dir: Path, data_dir: Path, dest: Paths, main: str,
            alts: dict[str, Path], region: str = "eu", ruleset: int = 2,
            faction: str = "alliance") -> list[str]:
    """Copy stock, bags, house, prices and game data; write a profile if there is none.

    region, ruleset and faction go into the new profile and the saved house."""
    actions: list[str] = []
    _copy(Path(user_dir) / "stock.toml", dest.character(main) / "stock.toml", actions)
    _add_goals(dest.character(main) / "stock.toml", actions)
    for name, bags in alts.items():
        _copy(Path(bags), dest.character(name) / "bags.toml", actions)
    house_file = Path(data_dir) / "house.json"
    if house_file.exists():
        house = int(json.loads(house_file.read_text(encoding="utf-8"))["house"])
        profile.save_house(dest.house, house, region, ruleset)
        actions.append(f"saved house {house} -> {dest.house}")
    _copy(Path(data_dir) / "prices.json", dest.prices, actions)
    gd = Path(data_dir) / "gamedata"
    if gd.is_dir():
        for f in sorted(gd.iterdir()):
            if f.is_file():
                _copy(f, dest.gamedata / f.name, actions)
    if dest.profile.exists():
        actions.append(f"kept {dest.profile}")
    else:
        # Quoted keys: character names may have spaces or accents, which bare TOML keys can't.
        chars = "".join(f'\n[characters.{json.dumps(n, ensure_ascii=False)}]\nfavor_standing = "Neutral"\n'
                        for n in [main, *alts])
        dest.profile.parent.mkdir(parents=True, exist_ok=True)
        dest.profile.write_text(f'region = "{region}"\nruleset = {ruleset}\nfaction = "{faction}"\n' + chars,
                                encoding="utf-8")
        actions.append(f"wrote {dest.profile}")
    return actions
