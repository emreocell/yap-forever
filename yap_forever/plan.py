"""Write the Blacksmithing + Enchanting plan report.

Usage: python3 plan.py
"""
import sys
from datetime import date

from yap_forever import gamedata
from yap_forever import settings
from yap_forever.config import load_stock
from yap_forever.costmodel import Valuer
from yap_forever.favor import load_favor
from yap_forever.guide import render_guide
from yap_forever.quests import load_quest_plans
from yap_forever.planner import plan
from yap_forever.prices import Market
from yap_forever.report import render, verdict


def main() -> int:
    p = settings.paths()
    if not p.prices.exists():
        print("No prices yet: run prices.py first.")
        return 1
    gamedata.fetch_all()
    gd = gamedata.load_gamedata()
    stock = load_stock(p.root / "stock.toml")
    favor = load_favor()
    market = Market.load()
    route = plan(gd, Valuer(market, gd, stock), stock, favor, cap=stock.target, quests=load_quest_plans())
    v = verdict(route, stock)
    out = p.reports / f"{date.today().isoformat()}-plan.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(route, v, market, gd, stock, favor), encoding="utf-8")
    g = out.with_name(f"{date.today().isoformat()}-guide.md")
    g.write_text(render_guide(route, gd, market, stock), encoding="utf-8")
    print(f"{v}. Guide: {g}  Full report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
