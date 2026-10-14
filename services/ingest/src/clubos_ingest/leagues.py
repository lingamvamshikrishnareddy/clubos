"""Loads real league structures and rules from packages/leagues/leagues.json.

  clubos-leagues load [--league nfl --league ipl ...]

Creates or updates each competition (matched on its reference key), its conferences,
divisions and teams, and links provider competition IDs (e.g. StatsBomb's Premier League)
to the same competition so connectors load into it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

REFERENCE_SOURCE = "clubos_reference"


def leagues_file() -> Path:
    if override := os.environ.get("CLUBOS_LEAGUES_FILE"):
        return Path(override)
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for parent in start.parents:
            candidate = parent / "packages" / "leagues" / "leagues.json"
            if candidate.is_file():
                return candidate
    raise FileNotFoundError("packages/leagues/leagues.json not found; set CLUBOS_LEAGUES_FILE")


def reference_leagues() -> dict[str, dict[str, Any]]:
    return {league["key"]: league for league in json.loads(leagues_file().read_text())["leagues"]}


def _entity(conn: psycopg.Connection, source: str, kind: str, external_id: str) -> Any:
    row = conn.execute(
        "select entity_id from source_entity_ids where source_id = %s and entity_type = %s and external_id = %s",
        (source, kind, external_id)).fetchone()
    return row[0] if row else None


def _link(conn: psycopg.Connection, source: str, kind: str, external_id: str, entity_id: Any) -> None:
    conn.execute(
        "insert into source_entity_ids (source_id, entity_type, external_id, entity_id) values (%s, %s, %s, %s)"
        " on conflict (source_id, entity_type, external_id) do nothing",
        (source, kind, external_id, entity_id))


def ensure_league(conn: psycopg.Connection, key: str) -> tuple[Any, dict[str, Any]]:
    """Creates or updates one league. Returns (competition_id, {team short name: team_id})."""
    league = reference_leagues()[key]
    competition_id = conn.execute(
        """
        insert into competitions (sport_id, name, country, gender, tier, is_youth, attributes, reference_key, pyramid, rules)
        values (%s, %s, %s, %s, %s, false, %s, %s, %s, %s)
        on conflict (reference_key) do update set
          name = excluded.name, country = excluded.country, gender = excluded.gender, tier = excluded.tier,
          attributes = competitions.attributes || excluded.attributes, pyramid = excluded.pyramid, rules = excluded.rules
        returning id
        """,
        (league["sport"], league["name"], league["country"], league["gender"], league["tier"],
         Jsonb(league.get("attributes", {})), key, league.get("pyramid"), Jsonb(league["rules"]))).fetchone()[0]

    teams: dict[str, Any] = {}

    def add_group(group: dict[str, Any], parent_id: Any) -> None:
        group_id = conn.execute(
            "insert into competition_groups (competition_id, parent_id, kind, name) values (%s, %s, %s, %s)"
            " on conflict (competition_id, name) do update set parent_id = excluded.parent_id, kind = excluded.kind"
            " returning id", (competition_id, parent_id, group["kind"], group["name"])).fetchone()[0]
        for short, name in group.get("teams", []):
            team_id = _entity(conn, REFERENCE_SOURCE, "team", f"{key}:{short}")
            if team_id is None:
                team_id = conn.execute(
                    "insert into teams (sport_id, name, country, short_name) values (%s, %s, %s, %s) returning id",
                    (league["sport"], name, league["country"], short)).fetchone()[0]
                _link(conn, REFERENCE_SOURCE, "team", f"{key}:{short}", team_id)
            else:
                conn.execute("update teams set name = %s, short_name = %s where id = %s", (name, short, team_id))
            conn.execute(
                "insert into competition_group_teams (group_id, team_id, from_season) values (%s, %s, %s)"
                " on conflict (group_id, team_id) do nothing", (group_id, team_id, league["rules"].get("season")))
            teams[short] = team_id
        for child in group.get("children", []):
            add_group(child, group_id)

    for group in league["structure"].get("groups", []):
        add_group(group, None)

    # Provider competition IDs that should load into this competition.
    for competition, _season in league.get("sources", {}).get("statsbomb", []):
        _link(conn, "statsbomb_open_data", "competition", str(competition), competition_id)
    return competition_id, teams


def load_leagues(conn: psycopg.Connection, keys: list[str] | None = None) -> dict[str, Any]:
    result = {key: ensure_league(conn, key)[0] for key in (keys or list(reference_leagues()))}
    conn.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("load")
    load.add_argument("--league", action="append", choices=sorted(reference_leagues()))
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is not set")
    with psycopg.connect(database_url) as conn:
        for key, competition_id in load_leagues(conn, args.league).items():
            print(f"{key:<18} {competition_id}")


if __name__ == "__main__":
    main()
