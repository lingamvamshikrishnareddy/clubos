# Leagues and real data

Real competitions are defined in [`packages/leagues/leagues.json`](../packages/leagues/leagues.json)
and loaded with `clubos-leagues load`. Each league has its structure, such as conferences, divisions
and its place in a promotion/relegation pyramid, and its **rules for a named season**. Rules
change every year, so update the file at the start of each season.

| League | Sport | Structure | Rules modelled | Real data connector |
|---|---|---|---|---|
| NFL | American football | 2 conferences, 8 divisions, 32 teams | Hard salary cap, 53-man roster, win-percentage standings | `clubos-ingest-nflverse load <season>` (nflverse, CC BY 4.0) |
| NBA | Basketball | 2 conferences, 6 divisions, 30 teams | Soft cap, luxury tax line, first and second aprons, 15 standard contracts | None yet: needs a licensed source |
| IPL | Cricket (T20) | 10 teams, top-four playoffs | Auction purse, squad 18–25, overseas limits (8 in squad, 4 in the XI), 2 points per win | `clubos-ingest-cricsheet load <ipl_json.zip>` (Cricsheet) |
| Premier League | Soccer | 20 teams, tier 1 of the English pyramid | Points (3/1/0), 3 relegated | StatsBomb open data where published (e.g. 2015/16) |
| EFL Championship, League One, League Two | Soccer | 24 teams each, tiers 2–4 | Points, automatic promotion and playoff places, relegation | None yet: needs a licensed source (Opta, Wyscout, StatsBomb) |

## How rules are used

- **Standings:** `v_league_table` ranks regular-season matches by each league's rule: points for football and cricket, win percentage for the NFL and NBA.
- **Roster checks:** `checkRoster` and `checkPlannedRoster` in `packages/core` check a roster or a planned window against salary caps (hard or soft, with tax and apron tiers), auction purses, squad sizes and overseas-player limits.
  - When a player's nationality is unknown, the check reports that it cannot confirm the limit; it never guesses.
- **Pyramids:** `competitions.pyramid` and `tier` record league pyramids, and the rules name where teams are promoted and relegated to.

## Connector notes

### NFL (nflverse)

- **What's loaded:** games (regular season and playoffs), play-by-play, regular-season snap counts (as playing time) and player profiles.
- **Matches the official numbers:** for 2024, rushing, passing, sack and tackle totals match the official season figures.
- **Not in the open data, so left absent:**
  - pressures (only hits and sacks are available)
  - pass-block win rate
  - coverage stats
  - drops
  - missed tackles
- **Defensive credit:** goes to the tackler's own team, on scrimmage plays only.

### IPL (Cricsheet)

- **Ball-by-ball:** every delivery is loaded with bowler and batter, so `v_cricket_matchups` covers real batter-vs-bowler records.
- **Excluded:** super overs, like football shoot-outs.
- **Not in Cricsheet:**
  - pitch maps and wagon-wheel coordinates
  - bowling style (specialist bowlers get the style-neutral `bowler` role)
  - the wicketkeeper flag
- **Home side:** Cricsheet doesn't mark one, so the first listed team is stored as home.

### Football (StatsBomb)

- Competitions linked in `leagues.json`, such as the Premier League, load into the same competition, so they get its rules.

## Network access

Cloud environments may block some hosts. If `cricsheet.org` is blocked, add it to the environment's allowed domains, or download `ipl_json.zip` elsewhere and pass the file path.
