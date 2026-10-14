# Demo data

`clubos-mock-data` (in `services/ingest`) fills an empty database with **fictional** data for
all six sports. Generation is deterministic: the same `--seed` and `--as-of` always produce the
same data. Everything is recorded under the `mock` data source, so it can never be confused
with real data. All names of people, clubs, leagues and sponsors are invented.

## Per sport

- **League.** One league with 10 teams and two completed seasons of fixtures and results. Scoring follows each sport, from soccer's ~2.7 goals a game to T20 cricket's ~335 runs. League settings are in `services/ingest/src/clubos_ingest/mock_config.py`.
- **Players.** Full rosters for every team, sized and structured for the sport (for example a 26-player soccer squad, 51 in American football, 15 in basketball). Each player has sport-specific attributes such as preferred foot, bats and throws, shooting side, or bowling style.
- **Season stats.** Values for each role's comparison metrics, generated within the typical ranges in `sport.json` and driven by a hidden ability rating. Players develop between seasons, and smaller samples are noisier.
- **Market transactions.** About 40% of players have a recent move: transfers, trades, drafts, free-agent signings or auctions, depending on the sport. The valuation model learns from these.

## The demo club (one per sport)

| Area | What's included |
|---|---|
| Staff | 11 users with roles and departments: sporting director, coaches, analyst, scouts, performance, medical, finance, executive |
| Squad | Roster, statuses, contracts with fees and clauses; 10 academy players with guardians |
| Recruitment | Club style profiles for 3 roles; 14 scouting reports; 2 shortlists |
| Video | 3 match videos with 40 tagged events each, clips, playlists, tactical report |
| Performance | 6 weeks of sessions with RPE and sport-specific external load; daily wellness; three players with a recent load spike; injuries and modified training |
| Operations | Calendar, attendance, tasks, announcements, facilities and bookings |
| Play-by-play | The club's last three games, simulated per sport: soccer passes and shots; basketball shots, free throws and stints; hockey shots and line shifts; cricket ball-by-ball; baseball pitch-by-pitch; American football plays. Match scores are set from these events. |
| Business | Budgets, monthly costs, sponsors and deals, advertising inventory and bookings, home-game and stadium-hire revenue, academy fees, payments and renewals, monthly payroll with payslips |
| Decisions and messages | Decisions (signing, renewal, return to play, commercial), some with reviewed outcomes; staff message threads |

Model outputs are computed by `clubos-ml run` from this data; they are never generated directly.

## Usage

```sh
DATABASE_URL=postgresql://localhost/clubos_demo uv run clubos-mock-data --as-of 2026-10-14 [--sport cricket ...]
```

The command refuses to run against a database that already has organisations.
