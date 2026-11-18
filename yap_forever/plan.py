"""Write the Blacksmithing + Enchanting plan report.

Usage: python3 plan.py
"""
import sys
from datetime import date

from yap_forever import gamedata
from yap_forever.config import USER_DIR, load_stock
from yap_forever.costmodel import Valuer
from yap_forever.favor import load_favor
from yap_forever.guide import render_guide
from yap_forever.quests import load_quest_plans
from yap_forever.planner import plan
from yap_forever.prices import PRICES_PATH, Market
from yap_forever.report import render, verdict


def main() -> int:
    if not PRICES_PATH.exists():
        print("No prices yet: run prices.py first.")
        return 1
    gamedata.fetch_all()
    gd = gamedata.load_gamedata()
    stock = load_stock()
    favor = load_favor()
    market = Market.load()
    p = plan(gd, Valuer(market, gd, stock), stock, favor, cap=stock.target, quests=load_quest_plans())
    v = verdict(p, stock)
    out = USER_DIR / "reports" / f"{date.today().isoformat()}-plan.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(p, v, market, gd, stock, favor))
    g = out.with_name(f"{date.today().isoformat()}-guide.md")
    g.write_text(render_guide(p, gd, market, stock))
    print(f"{v}. Guide: {g}  Full report: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
