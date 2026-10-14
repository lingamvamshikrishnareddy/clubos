# Baseball reference

Generated from `packages/sports/baseball/sport.json` by `scripts/sport-docs.py`. Do not edit by hand.

## Exposure

- Default: **Plate appearances**, values shown per 600; low-sample below 150.
- `starting_pitcher`: **Batters faced**, per 600; low-sample below 200.
- `relief_pitcher`: **Batters faced**, per 600; low-sample below 80.

Valuation basis: **annual salary**.

## Roles and comparison metrics

| Role | Group | Compared on |
|---|---|---|
| Starting pitcher (`starting_pitcher`) | pitching | `era`, `fip`, `whip`, `k_per_9`, `bb_per_9`, `fastball_velocity`, `whiff_rate` |
| Relief pitcher (`relief_pitcher`) | pitching | `fip`, `k_per_9`, `bb_per_9`, `fastball_velocity`, `spin_rate`, `whiff_rate` |
| Catcher (`catcher`) | infield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `strikeout_rate`, `hard_hit_rate`, `outs_above_average` |
| First base (`first_base`) | infield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `strikeout_rate`, `hard_hit_rate`, `outs_above_average` |
| Second base (`second_base`) | infield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `strikeout_rate`, `hard_hit_rate`, `outs_above_average` |
| Third base (`third_base`) | infield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `strikeout_rate`, `hard_hit_rate`, `outs_above_average` |
| Shortstop (`shortstop`) | infield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `strikeout_rate`, `hard_hit_rate`, `outs_above_average` |
| Left field (`left_field`) | outfield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `stolen_bases`, `hard_hit_rate`, `outs_above_average` |
| Centre field (`centre_field`) | outfield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `stolen_bases`, `hard_hit_rate`, `outs_above_average` |
| Right field (`right_field`) | outfield | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `stolen_bases`, `hard_hit_rate`, `outs_above_average` |
| Designated hitter (`designated_hitter`) | hitting | `woba`, `on_base_pct`, `slugging_pct`, `home_runs`, `avg_exit_velocity`, `hard_hit_rate`, `strikeout_rate` |

## Metrics

| Key | Metric | Normalisation | Better | Typical | Description |
|---|---|---|---|---|---|
| `batting_avg` | Batting average | rate | higher | 0.21–0.31 | Hits / at-bats. |
| `on_base_pct` | On-base % | rate | higher | 0.28–0.39 | Times on base / plate appearances. |
| `slugging_pct` | Slugging % | rate | higher | 0.33–0.55 | Total bases / at-bats. |
| `woba` | wOBA | rate | higher | 0.28–0.39 | Weighted on-base average. |
| `home_runs` | Home runs | per exposure | higher | 3–40 | Home runs hit. |
| `strikeout_rate` | Strikeout % | rate | lower | 0.12–0.3 | Strikeouts / plate appearances. |
| `walk_rate` | Walk % | rate | higher | 0.05–0.14 | Walks / plate appearances. |
| `hard_hit_rate` | Hard-hit % | rate | higher | 0.3–0.52 | Batted balls at 95 mph or more. |
| `avg_exit_velocity` | Average exit velocity | rate | higher | 85–93 | Mean exit velocity of batted balls. |
| `stolen_bases` | Stolen bases | per exposure | higher | 0–35 | Bases stolen. |
| `outs_above_average` | Outs above average | total | higher | -8–12 | Range-based fielding value over the season. |
| `era` | ERA | rate | lower | 2.6–5.2 | Earned runs per nine innings. |
| `fip` | FIP | rate | lower | 2.8–5.0 | Fielding-independent pitching. |
| `whip` | WHIP | rate | lower | 0.95–1.5 | Walks plus hits per inning pitched. |
| `k_per_9` | K/9 | rate | higher | 6–12.5 | Strikeouts per nine innings. |
| `bb_per_9` | BB/9 | rate | lower | 1.5–4.5 | Walks per nine innings. |
| `fastball_velocity` | Fastball velocity | rate | higher | 91–98.5 | Average four-seam fastball velocity. |
| `spin_rate` | Fastball spin rate | rate | higher | 2100–2550 | Average four-seam spin rate. |
| `whiff_rate` | Whiff % | rate | higher | 0.18–0.35 | Swings and misses / swings. |
| `ground_ball_rate` | Ground-ball % | rate | higher | 0.35–0.55 | Ground balls / batted balls allowed. |

## Event types

`pitch`, `swing`, `batted_ball`, `strikeout`, `walk`, `hit`, `home_run`, `stolen_base`, `defensive_play`, `error`

## Video tags

- **Pitch type** (`pitch_type`): four-seam fastball, sinker, cutter, slider, sweeper, curveball, changeup, splitter
- **Pitch location** (`location`): up and in, up and away, down and in, down and away, middle, chase
- **Count** (`count`): 0-0, ahead, behind, two strikes, full count
- **Batted ball** (`batted_ball`): ground ball, line drive, fly ball, pop-up, barrel
- **Defensive alignment** (`shift`): standard, infield in, no-doubles, strategic positioning
