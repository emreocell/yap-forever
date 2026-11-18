# Progress

One line per finished task. Plans are private to the owner; tasks are named by phase and number.

| Date | Phase.Task | What | PR |
|---|---|---|---|
| 2026-11-18 | 1.1 | Planner moved into the `yap_forever` package; licence; private-detail scan clean | (initial commit) |
| 2026-11-18 | 1.2 | Per-player home folder (`~/.yap-forever`, `YAP_FOREVER_HOME`), paths resolved at call time, credentials check skips POSIX modes on Windows, UTF-8 for every text read and write | #2 |
| 2026-11-18 | 1.3 | Profile (region, ruleset, faction, characters with Favor standing); API client for any region; probe scans every house in the ruleset index and leaves `house.json` alone unless exactly one house holds the marker | #3 |
| 2026-11-18 | 1.4 | Merchant's Favor catalogue as public data (`data_static/favor.toml`): 40 Neutral, 23 Friendly, 5 Honored recipes (Friendly/Honored disputed between guides); loaded for the character's standing | #4 |
| 2026-11-18 | 1.5 | One command line (`python3 -m yap_forever init/check/probe/prices/plan`); Python version check first; next-step messages use the right interpreter per system | #5 |
| 2026-11-18 | 1.6 | `migrate` command moves a pre-yap-forever planner folder into the home layout (never credentials). Reproduction: main guide and full report identical to the old planner; alt 2 shopping list identical except the dropped house line | #6 |
| 2026-11-18 | 1.7 | Plugin manifests, `forever-professions` skill with setup, list-layout and game-rules references, CREDITS, README; checks for manifests, skill links, credits and private details. Headless session with `--plugin-dir` loaded the skill and ran `check --offline` from the plugin root | #7 |
| 2026-11-18 | 1.8 | CI on Windows, macOS and Linux with Python 3.11 and 3.13; POSIX-mode tests skip on Windows; `__main__` safe on old Pythons (3.9 gets the version message); `llms.txt` and `HANDOFF.md` | #8 |
| 2026-11-18 | 1.9 | Final review fixes: network failures give a next step instead of a traceback; output escapes characters a Windows console code page cannot show; neutral house numbers in tests and a pattern-capable private denylist | #9 |
| 2026-11-18 | 1.10 | Two-word Forever character names: quoted TOML keys in `migrate`, the profile template and the setup guide | #10 |
| 2026-11-18 | 1.11 | Commit identity check (noreply after a baseline), stacked-PR rule in `AGENTS.md`, CI with full history and read-only permissions, setup record updated | #11 |
| 2026-11-18 | 1.12 | Plans start from the character's current skills (`[skills]` in `stock.toml`) and ranks already trained (independent review, finding 2) | #12 |
| 2026-11-18 | 1.13 | 15% buffer on yellow and green steps in the guide and report, rounded up; guide and report counts agree (independent review, finding 3) | #13 |
| 2026-11-18 | 1.14 | Prices record their house, region and ruleset; a refresh for another house downloads in full; commodities are checked apart from auctions; `plan` refuses prices from another house (independent review, finding 5) | #14 |
| 2026-11-18 | 1.15 | Bars that would be mined come first from ore, coal and bars in the bank (smelted, component bars in turn); banked coal counts at its value (independent review, finding 1) | #15 |
| 2026-11-18 | 1.16 | Disenchanting follows Forever: no item-level gate up to item level 45, and each disenchant is a chance at an Enchanting skill-up (1/20/40/60, matching play); greens are kept for disenchanting while that still gives skill (independent review, finding 4) | #16 |
| 2026-11-18 | 1.17 | Quest-learned recipes are skipped while the character is below the quest level, with the reason in the report (independent review, finding 6) | #17 |
| 2026-11-18 | 1.18 | Sales of leftover crafts count on the AH only up to what is listed today (and the sale limit); greens still kept for disenchanting are not counted as sold (independent review, finding 7) | #18 |
| 2026-11-18 | 1.19 | A damaged `prices.json` or `house.json` gives a next step in `check` and `plan`, and `prices` replaces a damaged price file; a cut-off or garbled API response is an API error; game data downloads to a temporary name and is renamed into place (independent review, finding 8) | #19 |
| 2026-11-18 | 1.20 | `migrate` takes `--region`, `--ruleset` and `--faction` (default EU, 2, Alliance) and writes them into the profile and the saved house (independent review, finding 9) | #20 |
| 2026-11-18 | 1.21 | Guide amounts keep one decimal of gold up to 100g, so 10g 50s no longer prints as 10g (independent review, finding 10) | #21 |
| 2026-11-18 | 1.22 | Follow-ups to findings 3 and 4: the 15% buffer is judged one skill point at a time, so a merged orange run (one profession levelling alone) gets none; disenchant counts carry no buffer and round to nearest, never more than the greens made; greens are kept for the skill-up only once Enchanting can disenchant them; disenchant steps checked in the guide and report | #22 |
| 2026-11-18 | 1.23 | Generic character names in the migrate test (the owner's names are now on the private denylist); first tag renamed to `v0.1.0-planner`; HANDOFF updated | #23 |
| 2026-11-18 | 1.24 | Greens in the bank are disenchanted first, all at once: free Enchanting skill-ups below 60 and materials for later Enchanting steps; shown as the first "Disenchant greens" step and in the keep table | #24 |
