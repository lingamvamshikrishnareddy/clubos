"""NFL seasons from nflverse (CC BY 4.0): games, play-by-play, snap counts and players.

  clubos-ingest-nflverse load <season> [--data-dir DIR]

Loads into the NFL competition from packages/leagues (teams matched by abbreviation).
Season stats cover what the open data supports; metrics it does not measure (pressures,
pass-block win rate, coverage, drops, missed tackles) are left absent, never zero.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import os
import sys
import urllib.request
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .leagues import ensure_league

SOURCE_ID = "nflverse"
BASE_URL = "https://github.com/nflverse/nflverse-data/releases/download"

# nflverse / Pro Football Reference positions -> American football role keys.
POSITION_ROLES = {
    "QB": "quarterback", "RB": "running_back", "FB": "running_back", "HB": "running_back",
    "WR": "wide_receiver", "TE": "tight_end",
    "T": "offensive_line", "OT": "offensive_line", "G": "offensive_line", "OG": "offensive_line",
    "C": "offensive_line", "OL": "offensive_line",
    "DT": "defensive_line", "NT": "defensive_line", "DL": "defensive_line",
    "DE": "edge_rusher", "OLB": "edge_rusher", "EDGE": "edge_rusher",
    "LB": "linebacker", "ILB": "linebacker", "MLB": "linebacker",
    "CB": "cornerback", "DB": "cornerback", "S": "safety", "FS": "safety", "SS": "safety", "SAF": "safety",
    "K": "kicker", "PK": "kicker", "P": "punter",
}
DEFENSIVE_ROLES = {"defensive_line", "edge_rusher", "linebacker", "cornerback", "safety"}

Fetch = Callable[[str], Iterable[dict[str, str]]]


def fetch_csv(path: str, data_dir: Path | None = None) -> Iterable[dict[str, str]]:
    """Reads a release file from a local directory if present, otherwise downloads it."""
    name = path.rsplit("/", 1)[-1]
    local = data_dir / name if data_dir else None
    if local and local.exists():
        raw = local.read_bytes()
    else:
        with urllib.request.urlopen(f"{BASE_URL}/{path}", timeout=600) as response:
            raw = response.read()
        if local:
            local.write_bytes(raw)
    text = gzip.decompress(raw).decode() if name.endswith(".gz") else raw.decode()
    return csv.DictReader(io.StringIO(text))


def _f(value: str | None) -> float | None:
    return float(value) if value not in (None, "", "NA") else None


def _down_label(down: int | None, to_go: float | None, yardline_100: float | None) -> str | None:
    if yardline_100 is not None and yardline_100 <= 20:
        return "red zone"
    if down is None or to_go is None:
        return None
    if down == 1:
        return "1st & 10"
    if down == 4:
        return "4th down"
    return f"{'2nd' if down == 2 else '3rd'} & {'long' if to_go > (6 if down == 2 else 5) else 'short'}"


def _outcome(row: dict[str, str], kind: str) -> str | None:
    if kind == "field_goal":
        return row["field_goal_result"] or None
    if kind == "punt":
        return "punt"
    if row["touchdown"] == "1":
        return "touchdown"
    if row["interception"] == "1":
        return "interception"
    if row["fumble_lost"] == "1":
        return "fumble"
    if kind == "sack":
        return "sack"
    if kind == "pass":
        return "complete" if row["complete_pass"] == "1" else "incomplete"
    return "gain"


def load_season(conn: psycopg.Connection, season: int, fetch: Fetch | None = None,
                data_dir: Path | None = None) -> Any:
    fetch = fetch or (lambda path: fetch_csv(path, data_dir))
    competition_id, teams = ensure_league(conn, "nfl")
    run_id = conn.execute("insert into ingestion_runs (source_id, notes) values (%s, %s) returning id",
                          (SOURCE_ID, f"NFL {season}")).fetchone()[0]
    conn.commit()
    try:
        records = _load(conn, run_id, competition_id, teams, season, fetch)
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


def _entity(conn: psycopg.Connection, kind: str, external_id: str) -> Any:
    row = conn.execute("select entity_id from source_entity_ids where source_id = %s and entity_type = %s and external_id = %s",
                       (SOURCE_ID, kind, external_id)).fetchone()
    return row[0] if row else None


def _link(conn: psycopg.Connection, kind: str, external_id: str, entity_id: Any) -> None:
    conn.execute("insert into source_entity_ids (source_id, entity_type, external_id, entity_id) values (%s, %s, %s, %s)",
                 (SOURCE_ID, kind, external_id, entity_id))


def _load(conn: psycopg.Connection, run_id: Any, competition_id: Any, teams: dict[str, Any], season: int,
          fetch: Fetch) -> int:
    plays = list(fetch(f"pbp/play_by_play_{season}.csv.gz"))
    snaps = list(fetch(f"snap_counts/snap_counts_{season}.csv"))
    gsis_ids = {p for row in plays for p in (row.get("passer_player_id"), row.get("receiver_player_id"),
                                             row.get("rusher_player_id"), row.get("kicker_player_id"),
                                             row.get("punter_player_id")) if p}
    pfr_ids = {row["pfr_player_id"] for row in snaps}
    people = [row for row in fetch("players/players.csv") if row["gsis_id"] in gsis_ids or row["pfr_id"] in pfr_ids]
    gsis_by_pfr = {row["pfr_id"]: row["gsis_id"] for row in people if row["pfr_id"] and row["gsis_id"]}

    # Season ----------------------------------------------------------------------------
    label = str(season)
    season_id = _entity(conn, "season", f"NFL:{season}")
    dates = sorted(row["game_date"] for row in plays if row.get("game_date"))
    if season_id is None:
        season_id = conn.execute(
            "insert into seasons (competition_id, label, starts_on, ends_on) values (%s, %s, %s, %s) returning id",
            (competition_id, label, dates[0], dates[-1])).fetchone()[0]
        _link(conn, "season", f"NFL:{season}", season_id)

    # Players --------------------------------------------------------------------------
    player_ids: dict[str, Any] = {}  # gsis id -> player id
    role_of: dict[str, str | None] = {}
    for person in people:
        gsis = person["gsis_id"] or f"pfr:{person['pfr_id']}"
        role = POSITION_ROLES.get(person["position"]) or POSITION_ROLES.get(person["position_group"])
        role_of[gsis] = role
        row = conn.execute("select player_id from player_identities where source_id = %s and external_id = %s",
                           (SOURCE_ID, gsis)).fetchone()
        if row:
            player_ids[gsis] = row[0]
            continue
        player_ids[gsis] = conn.execute(
            "insert into players (sport_id, full_name, birth_date, primary_role, attributes) values"
            " ('american_football', %s, %s, %s, %s) returning id",
            (person["display_name"], person["birth_date"] or None, role,
             Jsonb({k: v for k, v in (("height_in", _f(person["height"])), ("weight_lb", _f(person["weight"])),
                                      ("college", person["college_name"] or None)) if v is not None}))).fetchone()[0]
        conn.execute("insert into player_identities (source_id, external_id, player_id, match_method, confidence)"
                     " values (%s, %s, %s, 'exact', 1)", (SOURCE_ID, gsis, player_ids[gsis]))

    # Games ----------------------------------------------------------------------------
    games: dict[str, dict[str, Any]] = {}
    for row in plays:
        games.setdefault(row["game_id"], row)
    match_ids: dict[str, Any] = {}
    for game_id, row in games.items():
        home, away = teams[row["home_team"]], teams[row["away_team"]]
        stage = "regular" if row["season_type"] == "REG" else "playoff"
        values = (season_id, home, away, f"{row['game_date']}T00:00:00Z", int(row["home_score"]), int(row["away_score"]),
                  stage, f"Week {row['week']}")
        match_id = _entity(conn, "match", game_id)
        if match_id is None:
            match_id = conn.execute(
                "insert into matches (season_id, home_team_id, away_team_id, kickoff_at, home_score, away_score, stage, round)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s) returning id", values).fetchone()[0]
            _link(conn, "match", game_id, match_id)
        else:
            conn.execute("update matches set season_id = %s, home_team_id = %s, away_team_id = %s, kickoff_at = %s,"
                         " home_score = %s, away_score = %s, stage = %s, round = %s where id = %s", (*values, match_id))
        match_ids[game_id] = match_id

    # Season stats ---------------------------------------------------------------------------
    stats: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    games_played: dict[tuple[str, str], set] = defaultdict(set)
    snap_role: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in snaps:
        if row["game_type"] != "REG":
            continue  # season stats are regular season; snaps must match
        gsis = gsis_by_pfr.get(row["pfr_player_id"], f"pfr:{row['pfr_player_id']}")
        if gsis not in player_ids:
            continue
        key = (gsis, row["team"])
        role = POSITION_ROLES.get(row["position"])
        offence, defence = _f(row["offense_snaps"]) or 0, _f(row["defense_snaps"]) or 0
        snaps_here = defence if role in DEFENSIVE_ROLES else offence
        stats[key]["snaps"] += snaps_here
        if role:
            snap_role[key][role] += snaps_here or 1
        if snaps_here or _f(row["st_snaps"]):
            games_played[key].add(row["game_id"])

    def add(gsis: str | None, team: str, metric: str, amount: float = 1.0) -> None:
        if gsis and gsis in player_ids:
            stats[(gsis, team)][metric] += amount

    def yards_of(row: dict[str, str], column: str) -> float:
        return _f(row.get(column)) or 0.0

    for row in plays:
        offence, defence, kind = row["posteam"], row["defteam"], row["play_type"]
        if row["season_type"] != "REG" or not offence or row.get("two_point_attempt") == "1":
            continue
        if kind == "pass":
            passer = row["passer_player_id"]
            if row["sack"] == "1":
                add(row["sack_player_id"], defence, "sacks")
                add(row["half_sack_1_player_id"], defence, "sacks", 0.5)
                add(row["half_sack_2_player_id"], defence, "sacks", 0.5)
            elif row["pass_attempt"] == "1":
                complete = row["complete_pass"] == "1"
                add(passer, offence, "pass_attempts")
                add(passer, offence, "completions", 1 if complete else 0)
                add(passer, offence, "passing_yards", yards_of(row, "passing_yards"))
                add(passer, offence, "passing_tds", 1 if row["pass_touchdown"] == "1" else 0)
                add(passer, offence, "interceptions_thrown", 1 if row["interception"] == "1" else 0)
                receiver = row["receiver_player_id"]
                add(receiver, offence, "targets")
                if complete:
                    add(receiver, offence, "receptions")
                    add(receiver, offence, "receiving_yards", yards_of(row, "receiving_yards"))
                    add(receiver, offence, "yards_after_catch", yards_of(row, "yards_after_catch"))
            if (epa := _f(row["epa"])) is not None and passer:
                add(passer, offence, "epa_total", epa)
                add(passer, offence, "epa_plays")
        elif kind in ("run", "qb_kneel"):  # official rushing totals include kneel-downs
            rusher = row["rusher_player_id"]
            add(rusher, offence, "rushes")
            add(rusher, offence, "rushing_yards", yards_of(row, "rushing_yards"))
            if (epa := _f(row["epa"])) is not None:
                add(rusher, offence, "epa_total", epa)
                add(rusher, offence, "epa_plays")
        elif kind == "field_goal":
            add(row["kicker_player_id"], offence, "fg_attempts")
            add(row["kicker_player_id"], offence, "fg_made", 1 if row["field_goal_result"] == "made" else 0)
        elif kind == "punt" and row["punt_blocked"] != "1":
            add(row["punter_player_id"], offence, "punts")
            add(row["punter_player_id"], offence, "net_punt_yards", yards_of(row, "kick_distance") - yards_of(row, "return_yards"))
        if kind in ("pass", "run"):
            # Defensive credit on scrimmage plays, to the tackler's own team (turnover returns
            # can put offensive players in the tackle columns).
            for column in ("solo_tackle_1", "solo_tackle_2", "assist_tackle_1", "assist_tackle_2", "assist_tackle_3",
                           "assist_tackle_4", "tackle_with_assist_1", "tackle_with_assist_2"):
                add(row.get(f"{column}_player_id"), row.get(f"{column}_team") or defence, "tackles")
            for column in ("pass_defense_1_player_id", "pass_defense_2_player_id"):
                add(row.get(column), defence, "passes_defended")

    written = 0
    for (gsis, team), s in stats.items():
        role = max(snap_role[(gsis, team)], key=snap_role[(gsis, team)].get) if snap_role.get((gsis, team)) else role_of.get(gsis)
        if role is None or team not in teams or not s.get("snaps") and role not in ("kicker", "punter"):
            continue  # no regular-season snaps for this team: not a real player-team season
        exposure_unit, exposure = "snaps", s.get("snaps")
        if role == "kicker":
            exposure_unit, exposure = "kicks", s.get("fg_attempts")
        elif role == "punter":
            exposure_unit, exposure = "punts", s.get("punts")
        values: dict[str, float | None] = {}
        if s.get("pass_attempts"):
            values |= {"pass_attempts": s["pass_attempts"], "passing_yards": s["passing_yards"], "passing_tds": s["passing_tds"],
                       "interceptions_thrown": s["interceptions_thrown"],
                       "completion_pct": round(s["completions"] / s["pass_attempts"], 4)}
        if s.get("epa_plays"):
            values["epa_per_play"] = round(s["epa_total"] / s["epa_plays"], 4)
        if s.get("rushes"):
            values |= {"rushing_yards": s["rushing_yards"], "yards_per_carry": round(s["rushing_yards"] / s["rushes"], 3)}
        if s.get("targets"):
            values |= {"targets": s["targets"], "receptions": s.get("receptions", 0), "receiving_yards": s.get("receiving_yards", 0),
                       "yards_after_catch": s.get("yards_after_catch", 0)}
        if role in DEFENSIVE_ROLES:
            values |= {"tackles": s.get("tackles", 0), "sacks": s.get("sacks", 0), "passes_defended": s.get("passes_defended", 0)}
        if s.get("fg_attempts"):
            values["field_goal_pct"] = round(s["fg_made"] / s["fg_attempts"], 4)
        if s.get("punts"):
            values["net_punt_avg"] = round(s["net_punt_yards"] / s["punts"], 2)
        stats_id = conn.execute(
            "insert into player_season_stats (player_id, season_id, team_id, role_key, exposure, exposure_unit, appearances,"
            " source_id, source_record_id, ingestion_run_id) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " on conflict (player_id, season_id, team_id, source_id) do update set role_key = excluded.role_key,"
            " exposure = excluded.exposure, exposure_unit = excluded.exposure_unit, appearances = excluded.appearances,"
            " ingestion_run_id = excluded.ingestion_run_id, ingested_at = now() returning id",
            (player_ids[gsis], season_id, teams[team], role, exposure, exposure_unit,
             len(games_played.get((gsis, team), ())) or None, SOURCE_ID, f"{season}:{gsis}:{team}", run_id)).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(
                "insert into player_season_metric_values (season_stats_id, metric_key, value) values (%s, %s, %s)"
                " on conflict (season_stats_id, metric_key) do update set value = excluded.value",
                [(stats_id, k, v) for k, v in values.items()])
        written += 1

    # Play-by-play ---------------------------------------------------------------------------
    events = []
    for row in plays:
        kind = {"pass": "pass", "run": "rush", "field_goal": "field_goal", "punt": "punt"}.get(row["play_type"])
        if kind is None or not row["posteam"]:
            continue
        if kind == "pass" and row["sack"] == "1":
            kind = "sack"
        carrier = {"pass": row["passer_player_id"], "sack": row["passer_player_id"], "rush": row["rusher_player_id"],
                   "field_goal": row["kicker_player_id"], "punt": row["punter_player_id"]}[kind]
        yardline = _f(row["yardline_100"])
        yards = _f(row["yards_gained"])
        down = int(row["down"]) if row["down"] not in ("", "NA") else None
        to_go = _f(row["ydstogo"])
        attributes = {k: v for k, v in {
            "offensive_formation": "shotgun" if row["shotgun"] == "1" else "under centre",
            "down_distance": _down_label(down, to_go, yardline), "down": down, "to_go": to_go,
            "success": row["success"] == "1" if row["success"] not in ("", "NA") else None,
            "epa": _f(row["epa"]), "week": int(row["week"]), "pass_location": row["pass_location"] or None,
            "air_yards": _f(row["air_yards"]),
        }.items() if v is not None}
        outcome = _outcome(row, kind)
        start_x = 100 - yardline if yardline is not None else None
        events.append((
            match_ids[row["game_id"]], SOURCE_ID, f"{row['game_id']}:{row['play_id']}", int(float(row["play_id"])),
            int(row["qtr"]), 3600 - (_f(row["game_seconds_remaining"]) or 0) if int(row["qtr"]) <= 4 else None,
            teams.get(row["posteam"]), player_ids.get(carrier), player_ids.get(row["receiver_player_id"]) if kind == "pass" else None,
            kind, outcome, start_x, None,
            min(max(start_x + yards, 0), 100) if start_x is not None and yards is not None and kind in ("pass", "rush", "sack") else None,
            None, yards if kind in ("pass", "rush", "sack") else _f(row["kick_distance"]), Jsonb(attributes)))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into match_events (match_id, source_id, source_record_id, sequence, period, clock_seconds, team_id,"
            " player_id, related_player_id, event_type, outcome, x, y, end_x, end_y, value, attributes)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " on conflict (source_id, source_record_id) do update set outcome = excluded.outcome, value = excluded.value,"
            " attributes = excluded.attributes", events)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load")
    load.add_argument("season", type=int)
    load.add_argument("--data-dir", type=Path, help="Read or cache release files here (never inside the repository).")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is not set")
    with psycopg.connect(database_url) as conn:
        run_id = load_season(conn, args.season, data_dir=args.data_dir)
        status, records = conn.execute("select status, records_ingested from ingestion_runs where id = %s", (run_id,)).fetchone()
    print(f"ingestion run {run_id}: {status}, {records} player-season rows")


if __name__ == "__main__":
    main()
