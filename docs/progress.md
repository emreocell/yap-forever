# Progress

One line per finished task. Plans are private to the owner; tasks are named by phase and number.

| Date | Phase.Task | What | PR |
|---|---|---|---|
| 2026-11-18 | 1.1 | Planner moved into the `yap_forever` package; licence; private-detail scan clean | (initial commit) |
| 2026-11-18 | 1.2 | Per-player home folder (`~/.yap-forever`, `YAP_FOREVER_HOME`), paths resolved at call time, credentials check skips POSIX modes on Windows, UTF-8 for every text read and write | #2 |
| 2026-11-18 | 1.3 | Profile (region, ruleset, faction, characters with Favor standing); API client for any region; probe scans every house in the ruleset index and leaves `house.json` alone unless exactly one house holds the marker | #3 |
