"""Write the two-profession plan report and guide (today: Blacksmithing + Enchanting)."""
from datetime import date
from pathlib import Path

from yap_forever import gamedata
from yap_forever.config import load_stock
from yap_forever.costmodel import Valuer
from yap_forever.favor import load_favor
from yap_forever.guide import render_guide
from yap_forever.planner import plan
from yap_forever.prices import Market
from yap_forever.quests import load_quest_plans
from yap_forever.report import render, verdict
from yap_forever.settings import Paths


def write_reports(paths: Paths, stock_path: Path, standing: str) -> tuple[str, Path, Path]:
    """Plan from the player's prices and stock; return (verdict, guide path, full report path)."""
    gamedata.fetch_all(dest=paths.gamedata)
    gd = gamedata.load_gamedata(paths.gamedata)
    stock = load_stock(stock_path)
    favor = load_favor(standing)
    market = Market.load(paths.prices)
    route = plan(gd, Valuer(market, gd, stock), stock, favor, cap=stock.target, quests=load_quest_plans())
    v = verdict(route, stock)
    today = date.today().isoformat()
    out = paths.reports / f"{today}-plan.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(route, v, market, gd, stock, favor), encoding="utf-8")
    g = out.with_name(f"{today}-guide.md")
    g.write_text(render_guide(route, gd, market, stock), encoding="utf-8")
    return v, g, out
