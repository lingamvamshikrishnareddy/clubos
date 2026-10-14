# Association football reference

Generated from `packages/sports/soccer/sport.json` by `scripts/sport-docs.py`. Do not edit by hand.

## Exposure

- Default: **Minutes**, values shown per 90; low-sample below 450.

Valuation basis: **transfer fee**.

## Roles and comparison metrics

| Role | Group | Compared on |
|---|---|---|
| Goalkeeper (`goalkeeper`) | goalkeeping | `passes_attempted`, `passes_completed`, `progressive_passes` |
| Centre-back (`centre_back`) | defence | `tackles_won`, `interceptions`, `ball_recoveries`, `progressive_passes`, `passes_completed` |
| Full-back / wing-back (`full_back`) | defence | `progressive_passes`, `progressive_carries`, `key_passes`, `tackles_won`, `interceptions` |
| Defensive midfielder (`defensive_midfielder`) | midfield | `ball_recoveries`, `interceptions`, `tackles_won`, `pressures`, `progressive_passes` |
| Central midfielder (`central_midfielder`) | midfield | `progressive_passes`, `progressive_carries`, `key_passes`, `pressures`, `ball_recoveries` |
| Attacking midfielder (`attacking_midfielder`) | midfield | `xa`, `key_passes`, `np_xg`, `dribbles_completed`, `progressive_carries` |
| Winger (`winger`) | attack | `np_xg`, `xa`, `dribbles_completed`, `progressive_carries`, `key_passes` |
| Striker (`striker`) | attack | `np_xg`, `goals`, `shots`, `xa`, `pressures` |

## Metrics

| Key | Metric | Normalisation | Better | Typical | Description |
|---|---|---|---|---|---|
| `goals` | Goals | per exposure | higher | 0–0.6 | All goals scored, including penalties. |
| `np_xg` | Non-penalty xG | per exposure | higher | 0–0.6 | Sum of expected-goals values of non-penalty shots. |
| `shots` | Shots | per exposure | higher | 0.2–3.5 | All shot attempts. |
| `xa` | Expected assists | per exposure | higher | 0–0.35 | Sum of xG of shots directly assisted by the player's passes. |
| `key_passes` | Key passes | per exposure | higher | 0.1–2.5 | Passes directly leading to a shot. |
| `passes_attempted` | Passes attempted | per exposure | higher | 20–80 | All open-play and set-piece passes attempted. |
| `passes_completed` | Passes completed | per exposure | higher | 14–72 | Passes that reached a team-mate. |
| `progressive_passes` | Progressive passes | per exposure | higher | 1–9 | Completed passes starting outside the defensive 40% of the pitch that end at least 25% closer to the centre of the opponent's goal. |
| `progressive_carries` | Progressive carries | per exposure | higher | 0.5–6 | Carries starting outside the defensive 40% of the pitch that end at least 25% closer to the centre of the opponent's goal. |
| `dribbles_completed` | Successful dribbles | per exposure | higher | 0.1–3 | Take-ons that beat an opponent. |
| `pressures` | Pressures | per exposure | higher | 5–25 | Pressure actions applied to an opponent in possession. |
| `tackles_won` | Tackles won | per exposure | higher | 0.3–2.5 | Tackles that won the ball or put it out of play. |
| `interceptions` | Interceptions | per exposure | higher | 0.2–2 | Successful interceptions of opponent passes. |
| `ball_recoveries` | Ball recoveries | per exposure | higher | 3–10 | Loose balls recovered by the player. |

## Event types

`pass`, `carry`, `dribble`, `shot`, `pressure`, `duel`, `interception`, `ball_recovery`, `clearance`, `block`, `foul_committed`, `substitution`

## Video tags

- **Phase of play** (`phase`): build-up, progression, final third, counter-attack, counter-press, high press, mid block, low block, set piece
- **Formation** (`formation`): 4-3-3, 4-2-3-1, 4-4-2, 3-5-2, 3-4-3, 5-3-2
- **Set piece** (`set_piece`): corner, direct free kick, indirect free kick, throw-in, penalty, goal kick
- **Outcome** (`outcome`): goal, shot, chance created, turnover, foul won, regain
