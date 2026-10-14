"""IPL (and other Cricsheet competitions) from Cricsheet ball-by-ball JSON.

  clubos-ingest-cricsheet load <zip file, directory or URL> [--league ipl]

Cricsheet publishes one JSON file per match (https://cricsheet.org/downloads/, e.g.
ipl_json.zip). Loads matches, ball-by-ball deliveries (bowler vs batter) and season stats
into the league from packages/leagues. Super overs are excluded from stats, like
football shoot-outs. Cricsheet has no pitch-map or wagon-wheel coordinates, bowling style
or wicketkeeper flag, so those stay absent.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import urllib.request
import zipfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .leagues import ensure_league

SOURCE_ID = "cricsheet"
BOWLER_WICKETS = {"bowled", "caught", "caught and bowled", "lbw", "stumped", "hit wicket"}
PLAYOFF_STAGES = {"qualifier 1": "qualifier", "qualifier 2": "qualifier", "eliminator": "eliminator", "final": "final",
                  "semi final": "playoff", "elimination final": "eliminator"}


def read_matches(source: str | Path) -> Iterable[tuple[str, dict[str, Any]]]:
    """Yields (match id, match JSON) from a Cricsheet zip, a directory of JSON files, or a URL."""
    text = str(source)
    if text.startswith(("http://", "https://")):
        with urllib.request.urlopen(text, timeout=600) as response:
            source = io.BytesIO(response.read())
    elif Path(text).is_dir():
        for path in sorted(Path(text).glob("*.json")):
            yield path.stem, json.loads(path.read_text())
        return
    with zipfile.ZipFile(source) as archive:
        for name in sorted(archive.namelist()):
            if name.endswith(".json"):
                yield Path(name).stem, json.loads(archive.read(name))


def _phase(over: int) -> str:
    return "powerplay" if over < 6 else "death overs" if over >= 16 else "middle overs"


def assign_role(batting_positions: list[int], balls_faced: int, balls_bowled: int, matches: int) -> str | None:
    """Role from how a player was used. Bowling style is not in Cricsheet, so specialist
    bowlers get the style-neutral 'bowler' role."""
    if matches == 0:
        return None
    bowls = balls_bowled / matches >= 12  # two overs a game on average
    position = sum(batting_positions) / len(batting_positions) if batting_positions else None
    bats = position is not None and position <= 7 and balls_faced / matches >= 8
    if bowls and bats:
        return "all_rounder"
    if bowls:
        return "bowler"
    if position is None:
        return "bowler" if balls_bowled else None  # bowled a little and never batted
    if position <= 2.0:
        return "opening_batter"
    if position <= 3.5:
        return "top_order_batter"
    if position <= 5.5:
        return "middle_order_batter"
    return "finisher"


def _entity(conn: psycopg.Connection, kind: str, external_id: str) -> Any:
    row = conn.execute("select entity_id from source_entity_ids where source_id = %s and entity_type = %s and external_id = %s",
                       (SOURCE_ID, kind, external_id)).fetchone()
    return row[0] if row else None


def _link(conn: psycopg.Connection, kind: str, external_id: str, entity_id: Any) -> None:
    conn.execute("insert into source_entity_ids (source_id, entity_type, external_id, entity_id) values (%s, %s, %s, %s)",
                 (SOURCE_ID, kind, external_id, entity_id))


def load(conn: psycopg.Connection, source: str | Path, league_key: str = "ipl") -> Any:
    competition_id, reference_teams = ensure_league(conn, league_key)
    run_id = conn.execute("insert into ingestion_runs (source_id, notes) values (%s, %s) returning id",
                          (SOURCE_ID, f"{league_key} from {source}")).fetchone()[0]
    conn.commit()
    try:
        records = _load(conn, run_id, competition_id, reference_teams, read_matches(source))
    except BaseException as error:
        conn.rollback()
        conn.execute("update ingestion_runs set status = 'failed', finished_at = now(), notes = notes || %s where id = %s",
                     (f" | failed: {error!r}", run_id))
        conn.commit()
        raise
    conn.execute("update ingestion_runs set status = 'succeeded', finished_at = now(), records_ingested = %s where id = %s",
                 (records, run_id))
    conn.commit()
    return run_id


def _load(conn: psycopg.Connection, run_id: Any, competition_id: Any, reference_teams: dict[str, Any],
          matches: Iterable[tuple[str, dict[str, Any]]]) -> int:
    teams_by_name = {name: team_id for name, team_id in conn.execute(
        "select t.name, t.id from teams t where t.id = any(%s)", (list(reference_teams.values()),)).fetchall()}
    seasons: dict[str, Any] = {}
    players: dict[str, Any] = {}
    # Per (person, season, team): counting stats and usage for role assignment.
    stats: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(lambda: defaultdict(float))
    usage: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(lambda: {"positions": [], "matches": set()})
    loaded = 0

    def team_id(name: str) -> Any:
        if name not in teams_by_name:
            existing = _entity(conn, "team", name)
            teams_by_name[name] = existing or conn.execute(
                "insert into teams (sport_id, name, country) values ('cricket', %s, null) returning id", (name,)).fetchone()[0]
            if existing is None:
                _link(conn, "team", name, teams_by_name[name])
        return teams_by_name[name]

    def player_id(registry: dict[str, str], name: str) -> Any:
        person = registry.get(name, f"name:{name}")
        if person not in players:
            row = conn.execute("select player_id from player_identities where source_id = %s and external_id = %s",
                               (SOURCE_ID, person)).fetchone()
            if row:
                players[person] = row[0]
            else:
                players[person] = conn.execute(
                    "insert into players (sport_id, full_name) values ('cricket', %s) returning id", (name,)).fetchone()[0]
                conn.execute("insert into player_identities (source_id, external_id, player_id, match_method, confidence)"
                             " values (%s, %s, %s, %s, %s)",
                             (SOURCE_ID, person, players[person], "exact" if name in registry else "probabilistic",
                              1 if name in registry else 0.6))
        return players[person]

    for match_key, data in matches:
        info = data["info"]
        if info.get("match_type") not in ("T20", "IT20"):
            continue
        season = str(info["season"])
        if season not in seasons:
            seasons[season] = _entity(conn, "season", f"{competition_id}:{season}")
            if seasons[season] is None:
                seasons[season] = conn.execute(
                    "insert into seasons (competition_id, label) values (%s, %s) returning id", (competition_id, season)).fetchone()[0]
                _link(conn, "season", f"{competition_id}:{season}", seasons[season])
        season_id = seasons[season]
        registry = info.get("registry", {}).get("people", {})
        team_names = info["teams"]
        # Cricsheet does not mark a home side; the first listed team is stored as home.
        home, away = team_id(team_names[0]), team_id(team_names[1])
        innings = [i for i in data.get("innings", []) if not i.get("super_over")]
        totals = {i["team"]: sum(d["runs"]["total"] for o in i["overs"] for d in o["deliveries"]) for i in innings}
        stage = PLAYOFF_STAGES.get(str(info.get("event", {}).get("stage", "")).lower(), "regular")
        values = (season_id, home, away, f"{info['dates'][0]}T00:00:00Z", totals.get(team_names[0]), totals.get(team_names[1]),
                  stage, str(info.get("event", {}).get("match_number") or info.get("event", {}).get("stage") or ""))
        match_id = _entity(conn, "match", match_key)
        if match_id is None:
            match_id = conn.execute(
                "insert into matches (season_id, home_team_id, away_team_id, kickoff_at, home_score, away_score, stage, round)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s) returning id", values).fetchone()[0]
            _link(conn, "match", match_key, match_id)
        else:
            conn.execute("update matches set season_id = %s, home_team_id = %s, away_team_id = %s, kickoff_at = %s,"
                         " home_score = %s, away_score = %s, stage = %s, round = %s where id = %s", (*values, match_id))

        for squad_team, names in info.get("players", {}).items():
            for name in names:
                usage[(registry.get(name, f"name:{name}"), season, squad_team)]["matches"].add(match_key)
                player_id(registry, name)

        events = []
        sequence = 0
        for number, inns in enumerate(innings, start=1):
            batting = inns["team"]
            bowling = team_names[1] if batting == team_names[0] else team_names[0]
            order: list[str] = []
            for over in inns["overs"]:
                legal = 0
                for delivery in over["deliveries"]:
                    sequence += 1
                    batter, bowler = delivery["batter"], delivery["bowler"]
                    for name in (batter, delivery["non_striker"]):
                        if name not in order:
                            order.append(name)
                    extras = delivery.get("extras", {})
                    wide, no_ball = "wides" in extras, "noballs" in extras
                    runs_bat = delivery["runs"]["batter"]
                    if not wide and not no_ball:
                        legal += 1
                    b = stats[(registry.get(batter, f"name:{batter}"), season, batting)]
                    if not wide:
                        b["balls_faced"] += 1
                        b["dots_faced"] += runs_bat == 0
                    b["runs"] += runs_bat
                    b["fours"] += runs_bat == 4 and not delivery["runs"].get("non_boundary")
                    b["sixes"] += runs_bat == 6
                    w = stats[(registry.get(bowler, f"name:{bowler}"), season, bowling)]
                    if not wide and not no_ball:
                        w["balls_bowled"] += 1
                        w["dots_bowled"] += delivery["runs"]["total"] == 0
                    w["runs_conceded"] += runs_bat + extras.get("wides", 0) + extras.get("noballs", 0)
                    wicket = None
                    for out in delivery.get("wickets", []):
                        wicket = out
                        dismissed = stats[(registry.get(out["player_out"], f"name:{out['player_out']}"), season, batting)]
                        dismissed["dismissals"] += out["kind"] not in ("retired hurt", "retired not out")
                        if out["kind"] in BOWLER_WICKETS:
                            w["wickets"] += 1
                        if out["kind"] in ("caught", "caught and bowled"):
                            fielder = bowler if out["kind"] == "caught and bowled" else (out.get("fielders") or [{}])[0].get("name")
                            if fielder and not (out.get("fielders") or [{}])[0].get("substitute"):
                                stats[(registry.get(fielder, f"name:{fielder}"), season, bowling)]["catches"] += 1
                    extra_type = next((t for t in ("wides", "noballs", "byes", "legbyes", "penalty") if t in extras), None)
                    attributes = {"over": over["over"] + 1, "ball": legal, "runs_bat": runs_bat,
                                  "extras": delivery["runs"]["extras"], "phase": _phase(over["over"])}
                    if extra_type:
                        attributes["extra_type"] = {"wides": "wide", "noballs": "no_ball", "byes": "bye",
                                                    "legbyes": "leg_bye", "penalty": "penalty"}[extra_type]
                    if wicket:
                        attributes["dismissal"] = wicket["kind"]
                    events.append((match_id, SOURCE_ID, f"{match_key}:{number}:{over['over']}:{sequence}", sequence, number,
                                   None, team_id(bowling), player_id(registry, bowler), player_id(registry, batter), "delivery",
                                   "wicket" if wicket else "extra" if wide or no_ball else "runs",
                                   runs_bat + delivery["runs"]["extras"], Jsonb(attributes)))
            for position, name in enumerate(order, start=1):
                usage[(registry.get(name, f"name:{name}"), season, batting)]["positions"].append(position)
        with conn.cursor() as cur:
            cur.executemany(
                "insert into match_events (match_id, source_id, source_record_id, sequence, period, clock_seconds, team_id,"
                " player_id, related_player_id, event_type, outcome, value, attributes)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " on conflict (source_id, source_record_id) do nothing", events)
        loaded += 1

    # Season stats -----------------------------------------------------------------------
    written = 0
    for (person, season, team), s in stats.items():
        use = usage.get((person, season, team), {"positions": [], "matches": set()})
        matches_played = len(use["matches"]) or 1
        # Role stays unknown (null) for fielding-only seasons; their catches are still kept.
        role = assign_role(use["positions"], int(s["balls_faced"]), int(s["balls_bowled"]), matches_played)
        bowling_role = role == "bowler"
        exposure_unit = "balls_bowled" if bowling_role else "balls_faced"
        exposure = s["balls_bowled"] if bowling_role else s["balls_faced"]
        values: dict[str, float | None] = {"catches": s["catches"]}
        if s["balls_faced"]:
            values |= {"runs": s["runs"], "sixes": s["sixes"],
                       "batting_strike_rate": round(100 * s["runs"] / s["balls_faced"], 2),
                       "batting_average": round(s["runs"] / s["dismissals"], 2) if s["dismissals"] else None,
                       "boundary_pct": round((s["fours"] + s["sixes"]) / s["balls_faced"], 4),
                       "batting_dot_pct": round(s["dots_faced"] / s["balls_faced"], 4)}
        if s["balls_bowled"]:
            values |= {"wickets": s["wickets"], "economy_rate": round(s["runs_conceded"] / (s["balls_bowled"] / 6), 2),
                       "bowling_average": round(s["runs_conceded"] / s["wickets"], 2) if s["wickets"] else None,
                       "bowling_strike_rate": round(s["balls_bowled"] / s["wickets"], 2) if s["wickets"] else None,
                       "bowling_dot_pct": round(s["dots_bowled"] / s["balls_bowled"], 4)}
        stats_id = conn.execute(
            "insert into player_season_stats (player_id, season_id, team_id, role_key, exposure, exposure_unit, appearances,"
            " source_id, source_record_id, ingestion_run_id) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " on conflict (player_id, season_id, team_id, source_id) do update set role_key = excluded.role_key,"
            " exposure = excluded.exposure, exposure_unit = excluded.exposure_unit, appearances = excluded.appearances,"
            " ingestion_run_id = excluded.ingestion_run_id, ingested_at = now() returning id",
            (players[person], seasons[season], teams_by_name[team], role, exposure, exposure_unit, len(use["matches"]) or None,
             SOURCE_ID, f"{season}:{person}:{team}", run_id)).fetchone()[0]
        with conn.cursor() as cur:
            # Undefined rates (no dismissals or no wickets) are left out, not stored as zero.
            cur.executemany(
                "insert into player_season_metric_values (season_stats_id, metric_key, value) values (%s, %s, %s)"
                " on conflict (season_stats_id, metric_key) do update set value = excluded.value",
                [(stats_id, k, v) for k, v in values.items() if v is not None])
        if role:
            conn.execute("update players set primary_role = coalesce(primary_role, %s) where id = %s", (role, players[person]))
        written += 1
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    load_cmd = commands.add_parser("load")
    load_cmd.add_argument("source", help="Cricsheet zip, directory of match JSON files, or download URL")
    load_cmd.add_argument("--league", default="ipl")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is not set")
    with psycopg.connect(database_url) as conn:
        run_id = load(conn, args.source, args.league)
        status, records = conn.execute("select status, records_ingested from ingestion_runs where id = %s", (run_id,)).fetchone()
    print(f"ingestion run {run_id}: {status}, {records} player-season rows")


if __name__ == "__main__":
    main()
