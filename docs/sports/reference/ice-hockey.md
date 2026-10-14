# Ice hockey reference

Generated from `packages/sports/ice-hockey/sport.json` by `scripts/sport-docs.py`. Do not edit by hand.

## Exposure

- Default: **Time on ice (min)**, values shown per 60; low-sample below 200.
- `goaltender`: **Shots against**, per 30; low-sample below 300.

Valuation basis: **annual salary**.

## Roles and comparison metrics

| Role | Group | Compared on |
|---|---|---|
| Centre (`centre`) | forward | `ixg`, `primary_assists`, `faceoff_win_pct`, `controlled_zone_entries`, `takeaways`, `xg_for_pct` |
| Winger (`winger`) | forward | `ixg`, `goals`, `primary_assists`, `shots`, `controlled_zone_entries`, `xg_for_pct` |
| Defenceman (`defenceman`) | defence | `controlled_zone_exits`, `blocked_shots`, `giveaways`, `takeaways`, `xg_for_pct`, `shots` |
| Goaltender (`goaltender`) | goaltending | `save_pct`, `goals_saved_above_expected`, `high_danger_save_pct` |

## Metrics

| Key | Metric | Normalisation | Better | Typical | Description |
|---|---|---|---|---|---|
| `goals` | Goals | per exposure | higher | 0.1–1.5 | Goals scored. |
| `primary_assists` | Primary assists | per exposure | higher | 0.1–1.2 | First assists on goals. |
| `shots` | Shots on goal | per exposure | higher | 3–12 | Shots on target. |
| `ixg` | Individual xG | per exposure | higher | 0.2–1.4 | Expected goals from own shots. |
| `controlled_zone_entries` | Controlled zone entries | per exposure | higher | 2–14 | Offensive-zone entries with possession. |
| `controlled_zone_exits` | Controlled zone exits | per exposure | higher | 2–16 | Defensive-zone exits with possession. |
| `takeaways` | Takeaways | per exposure | higher | 0.5–3 | Puck taken from the opponent. |
| `giveaways` | Giveaways | per exposure | lower | 0.5–3.5 | Puck lost to the opponent. |
| `blocked_shots` | Blocked shots | per exposure | higher | 0.5–6 | Opponent shots blocked. |
| `hits` | Hits | per exposure | higher | 1–10 | Body checks delivered. |
| `faceoff_win_pct` | Faceoff win % | rate | higher | 0.42–0.6 | Faceoffs won / taken. |
| `xg_for_pct` | xG for % | rate | higher | 0.42–0.58 | Team share of expected goals with the player on ice (5v5). |
| `save_pct` | Save % | rate | higher | 0.89–0.925 | Saves / shots against. |
| `goals_saved_above_expected` | Goals saved above expected | per exposure | higher | -0.6–0.6 | Expected goals against minus goals against. |
| `high_danger_save_pct` | High-danger save % | rate | higher | 0.78–0.87 | Saves on high-danger shots. |

## Event types

`shot`, `goal`, `faceoff`, `zone_entry`, `zone_exit`, `hit`, `block`, `takeaway`, `giveaway`, `penalty`, `save`, `line_change`

## Video tags

- **Game state** (`strength`): 5v5, power play, penalty kill, 4v4, 3v3, empty net
- **Forecheck** (`forecheck`): 1-2-2, 2-1-2, 1-3-1, trap
- **Zone entry** (`entry_type`): carry, dump-in, pass, failed
- **Shot danger** (`shot_danger`): high, medium, low
- **Defensive zone structure** (`defensive_structure`): box +1, swarm, man-on-man, collapsing
