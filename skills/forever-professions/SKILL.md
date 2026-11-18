---
name: forever-professions
description: Plan WoW: Forever profession levelling from the player's own auction house prices - cheapest craft route, shopping list, mailbox trips, Merchant's Favor recipes. Use when a player asks how to level a crafting profession on WoW: Forever (Blacksmithing, Enchanting, Leatherworking, Tailoring, Alchemy, Engineering), what to buy for it, what it will cost, or wants their yap-forever prices or setup checked.
---

# Forever professions

You plan WoW: Forever professions with the yap-forever planner. **The planner computes every
number; you never work out routes, counts or costs yourself.** Your job is setup, asking the
player what changed, running the planner, and walking them through the result.

## Running the planner

- The code lives at the plugin root: two folders above this skill's base directory (the
  directory you were given when this skill loaded). `cd` there before every command.
- Find the Python command once per session: on Windows try `py -3`, otherwise `python3`, then
  `python`; keep the first whose `--version` says 3.11 or newer. Below it is written `<python>`.
- Run `<python> -m yap_forever <command>`. Commands: `init`, `check [--offline]`,
  `probe --item ID --buyout COPPER`, `prices`, `plan --character "FIRST LAST"` (Forever character
  names are two words; quote them).
- The player's files are in `~/.yap-forever/` (or `$YAP_FOREVER_HOME`).
- **Never open, print or ask for `credentials.json`.** The player pastes their API client ID and
  secret into it themselves. If they paste them into the chat, tell them to create a new secret
  at develop.battle.net.

## Workflow

1. **Setup, if needed.** Run `check --offline`. For every `MISSING` line, follow
   [references/setup.md](references/setup.md) with the player, one step at a time.
2. **Ask what changed** since the last plan: level, profession skills, gold, Favor standing,
   free bag slots, and what has piled up (greens to disenchant, leftover materials). Update their
   character's `stock.toml` with what they confirm.
3. **Refresh prices** with `prices`. Prices update about once an hour.
4. **Run the planner** for what they asked: `plan --character NAME`.
5. **Walk through the result** top-down, craft by craft, as laid out in
   [references/list-layout.md](references/list-layout.md). When game data and play experience
   disagree, quote [references/game-rules.md](references/game-rules.md) and go with the rules.
6. **Save what they confirm** (new skills, stock) so the next plan starts from it.

## What the planner covers today

- Two professions at once (Blacksmithing and Enchanting by default) from a character's
  `stock.toml`, to the `target` skill set there.
- Merchant's Favor recipes for the character's standing (Alliance, Blacksmithing and
  Enchanting).
- Shopping lists for other professions to 150 via `<python> -m yap_forever.scripts.four_profs`
  and `.shopping`. These still need hand-holding.
- Not yet: trainer stops on route rows, legacy talents, Horde trainer locations, gear. Say so
  when asked, rather than guessing.
