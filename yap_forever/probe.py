"""Check API access and find which Alliance house is ours via a marker listing.

Usage: python3 probe.py [--token-only]
"""
import json
import sys
from datetime import datetime, timezone

from yap_forever import bnet
from yap_forever.config import DATA_DIR, load_credentials, load_stock


def main(argv: list[str]) -> int:
    try:
        client = bnet.Client(load_credentials())
        client.token()
    except (PermissionError, ValueError) as e:
        print(e)
        return 2
    except bnet.AuthError:
        print(bnet.AUTH_MESSAGE)
        return 2
    print("token OK")
    if "--token-only" in argv:
        return 0

    try:
        idx = client.get(f"/data/wow/ruleset/{bnet.RULESET}/auctions/index").body or {}
        print("houses in index:", ", ".join(str(h.get("id")) for h in idx.get("auctions", [])))
        stock = load_stock()
        if not stock.marker:
            print("Set [marker] item_id and buyout_copper in stock.toml first.")
            return 1
        houses = {}
        for h in bnet.HOUSES:
            regular = client.get(bnet.house_path(h)).body or {}
            comm = client.get(bnet.house_path(h, commodities=True)).body or {}
            houses[h] = (regular, comm)
            print(f"house {h}: {len(regular.get('auctions', []))} listings, "
                  f"{len(comm.get('auctions', []))} commodity listings")
    except bnet.AuthError:
        print(bnet.AUTH_MESSAGE)
        return 2
    except bnet.ApiError as e:
        print(e if e.status == 0 else f"{e} — the Forever API route may have changed.")
        return 1

    matches = bnet.find_marker(houses, *stock.marker)
    if len(matches) != 1:
        print(f"marker found in {len(matches)} houses ({matches}); the snapshot may not include it yet. "
              "Try again later or pick a more unusual buyout.")
        return 1
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / "house.json").write_text(json.dumps(
        {"house": matches[0], "found": datetime.now(timezone.utc).isoformat(timespec="seconds")}))
    print(f"Your auction house is {matches[0]} (saved to data/house.json).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
