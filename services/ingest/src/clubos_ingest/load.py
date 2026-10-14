"""Load a StatsBomb open-data competition-season into Postgres.

Every run is recorded in ingestion_runs. Provider IDs map to internal rows through
source_entity_ids (competitions, seasons, teams, matches) and player_identities
(players), so loading the same data again updates rows instead of duplicating them.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .statsbomb import SHOOTOUT_PERIOD, SOURCE_ID, aggregate_match, role_for_position

BASE_URL = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"

Fetch = Callable[[str], Any]


def fetch_json(path: str) -> Any:
    with urllib.request.urlopen(f"{BASE_URL}/{path}", timeout=120) as response:
        return json.load(response)


GENDERS = {"male": "men", "female": "women"}


def _entity_id(cur: psycopg.Cursor, entity_type: str, external_id: str) -> Any:
    cur.execute(
        "select entity_id from source_entity_ids"
        " where source_id = %s and entity_type = %s and external_id = %s",
        (SOURCE_ID, entity_type, external_id),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _remember(cur: psycopg.Cursor, entity_type: str, external_id: str, entity_id: Any) -> None:
    cur.execute(
        "insert into source_entity_ids (source_id, entity_type, external_id, entity_id)"
        " values (%s, %s, %s, %s)",
        (SOURCE_ID, entity_type, external_id, entity_id),
    )


def _upsert_competition(cur: psycopg.Cursor, meta: dict[str, Any]) -> Any:
    external_id = str(meta["competition_id"])
    values = (
        meta["competition_name"],
        meta.get("country_name"),
        GENDERS.get(meta.get("competition_gender", "")),
        bool(meta.get("competition_youth", False)),
    )
    if (competition_id := _entity_id(cur, "competition", external_id)) is not None:
        cur.execute(
            "update competitions set name = %s, country = %s, gender = %s, is_youth = %s"
            " where id = %s",
            (*values, competition_id),
        )
        return competition_id
    cur.execute(
        "insert into competitions (sport_id, name, country, gender, is_youth)"
        " values ('soccer', %s, %s, %s, %s) returning id",
        values,
    )
    competition_id = cur.fetchone()[0]
    _remember(cur, "competition", external_id, competition_id)
    return competition_id


def _upsert_season(cur: psycopg.Cursor, competition_id: Any, meta: dict[str, Any]) -> Any:
    external_id = f'{meta["competition_id"]}/{meta["season_id"]}'
    if (season_id := _entity_id(cur, "season", external_id)) is not None:
        return season_id
    cur.execute(
        "insert into seasons (competition_id, label) values (%s, %s) returning id",
        (competition_id, meta["season_name"]),
    )
    season_id = cur.fetchone()[0]
    _remember(cur, "season", external_id, season_id)
    return season_id


def _upsert_team(cur: psycopg.Cursor, external_id: str, name: str, country: str | None) -> Any:
    if (team_id := _entity_id(cur, "team", external_id)) is not None:
        return team_id
    cur.execute(
        "insert into teams (sport_id, name, country) values ('soccer', %s, %s) returning id",
        (name, country),
    )
    team_id = cur.fetchone()[0]
    _remember(cur, "team", external_id, team_id)
    return team_id


def _upsert_match(cur: psycopg.Cursor, season_id: Any, match: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Returns the match ID and a map of StatsBomb team ID -> internal team ID."""
    home, away = match["home_team"], match["away_team"]
    home_id = _upsert_team(
        cur, str(home["home_team_id"]), home["home_team_name"], home.get("country", {}).get("name")
    )
    away_id = _upsert_team(
        cur, str(away["away_team_id"]), away["away_team_name"], away.get("country", {}).get("name")
    )
    # StatsBomb kick-off times carry no time zone; they are stored as UTC until venue
    # time zones are modelled.
    kickoff = f'{match["match_date"]}T{match["kick_off"]}Z' if match.get("kick_off") else None
    values = (season_id, home_id, away_id, kickoff, match.get("home_score"), match.get("away_score"))
    external_id = str(match["match_id"])
    if (match_id := _entity_id(cur, "match", external_id)) is not None:
        cur.execute(
            "update matches set season_id = %s, home_team_id = %s, away_team_id = %s,"
            " kickoff_at = %s, home_score = %s, away_score = %s where id = %s",
            (*values, match_id),
        )
    else:
        cur.execute(
            "insert into matches (season_id, home_team_id, away_team_id, kickoff_at, home_score, away_score)"
            " values (%s, %s, %s, %s, %s, %s) returning id",
            values,
        )
        match_id = cur.fetchone()[0]
        _remember(cur, "match", external_id, match_id)
    teams = {str(home["home_team_id"]): home_id, str(away["away_team_id"]): away_id}
    return match_id, teams


def _resolve_player(cur: psycopg.Cursor, source_player_id: str, name: str, role_key: str | None) -> Any:
    """Exact match on the provider's player ID; otherwise create the player and identity."""
    cur.execute(
        "select player_id from player_identities where source_id = %s and external_id = %s",
        (SOURCE_ID, source_player_id),
    )
    if row := cur.fetchone():
        return row[0]
    cur.execute(
        "insert into players (sport_id, full_name, primary_role) values ('soccer', %s, %s) returning id",
        (name, role_key),
    )
    player_id = cur.fetchone()[0]
    cur.execute(
        "insert into player_identities (source_id, external_id, player_id, match_method, confidence)"
        " values (%s, %s, %s, 'exact', 1)",
        (SOURCE_ID, source_player_id, player_id),
    )
    return player_id


def _load_match(cur: psycopg.Cursor, run_id: Any, season_id: Any, match: dict[str, Any], events: list[dict[str, Any]]) -> int:
    match_id, teams = _upsert_match(cur, season_id, match)
    rows = aggregate_match(match["match_id"], events)
    player_ids: dict[str, Any] = {}
    for stats in rows:
        role_key = role_for_position(stats.position)
        player_id = _resolve_player(cur, stats.source_player_id, stats.player_name, role_key)
        player_ids[stats.source_player_id] = player_id
        team_id = teams.get(stats.source_team_id) or _upsert_team(
            cur, stats.source_team_id, stats.team_name, None
        )
        cur.execute(
            "insert into player_match_appearances"
            " (player_id, match_id, team_id, role_key, minutes, source_id, source_record_id,"
            "  ingestion_run_id, ingested_at)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " on conflict (player_id, match_id, source_id) do update set"
            "  team_id = excluded.team_id, role_key = excluded.role_key, minutes = excluded.minutes,"
            "  source_record_id = excluded.source_record_id,"
            "  ingestion_run_id = excluded.ingestion_run_id, ingested_at = excluded.ingested_at"
            " returning id",
            (
                player_id, match_id, team_id, role_key, stats.minutes, SOURCE_ID,
                f"{stats.source_match_id}:{stats.source_player_id}", run_id, stats.ingested_at,
            ),
        )
        appearance_id = cur.fetchone()[0]
        cur.executemany(
            "insert into player_metric_values (appearance_id, metric_key, value) values (%s, %s, %s)"
            " on conflict (appearance_id, metric_key) do update set value = excluded.value",
            [(appearance_id, key, value) for key, value in stats.metrics.items()],
        )
    _store_events(cur, match_id, teams, player_ids, events)
    return len(rows)


def _scale(point: list[float] | None) -> tuple[float | None, float | None]:
    """StatsBomb 120 x 80 pitch -> 0–100 on both axes (already attacking towards x = 100)."""
    if not point:
        return None, None
    return round(min(point[0] / 1.2, 100), 2), round(min(point[1] / 0.8, 100), 2)


def _store_events(cur: psycopg.Cursor, match_id: Any, teams: dict[str, Any], player_ids: dict[str, Any],
                  events: list[dict[str, Any]]) -> None:
    """Passes and shots for passing networks, average positions, formations and shot maps.
    Shoot-outs are excluded, as in the stats."""
    rows = []
    for sequence, event in enumerate(events, start=1):
        kind = event["type"]["name"]
        if kind not in ("Pass", "Shot") or event.get("period") == SHOOTOUT_PERIOD or "player" not in event:
            continue
        player_id = player_ids.get(str(event["player"]["id"]))
        if player_id is None:
            continue
        x, y = _scale(event.get("location"))
        if kind == "Pass":
            p = event["pass"]
            end_x, end_y = _scale(p.get("end_location"))
            complete = "outcome" not in p
            receiver = player_ids.get(str(p["recipient"]["id"])) if complete and p.get("recipient") else None
            row = ("pass", "complete" if complete else "incomplete", receiver, end_x, end_y, None,
                   {"height": p.get("height", {}).get("name"), "body_part": p.get("body_part", {}).get("name")})
        else:
            shot = event["shot"]
            end_x, end_y = _scale(shot.get("end_location"))
            outcome = "goal" if shot.get("outcome", {}).get("name") == "Goal" else (shot.get("outcome", {}).get("name") or "").lower()
            row = ("shot", outcome, None, end_x, end_y, shot.get("statsbomb_xg"),
                   {"shot_type": shot.get("type", {}).get("name"), "body_part": shot.get("body_part", {}).get("name")})
        kind_key, outcome, related, end_x, end_y, value, attributes = row
        rows.append((match_id, SOURCE_ID, event["id"], sequence, event.get("period", 1),
                     event["minute"] * 60 + event.get("second", 0), teams.get(str(event["team"]["id"])), player_id,
                     related, kind_key, outcome, x, y, end_x, end_y, value, Jsonb({k: v for k, v in attributes.items() if v})))
    cur.executemany(
        "insert into match_events (match_id, source_id, source_record_id, sequence, period, clock_seconds, team_id,"
        " player_id, related_player_id, event_type, outcome, x, y, end_x, end_y, value, attributes)"
        " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " on conflict (source_id, source_record_id) do update set outcome = excluded.outcome,"
        " related_player_id = excluded.related_player_id, value = excluded.value",
        rows,
    )


def _refresh_season_stats(cur: psycopg.Cursor, run_id: Any, season_id: Any) -> None:
    """Rolls match appearances up into season stats. All StatsBomb metrics are counts or
    xG sums, so season values are sums; unknown minutes stay out of the exposure."""
    cur.execute(
        "insert into player_season_stats (player_id, season_id, team_id, role_key, exposure, exposure_unit,"
        " appearances, source_id, source_record_id, ingestion_run_id)"
        " select a.player_id, m.season_id, a.team_id, mode() within group (order by a.role_key), sum(a.minutes),"
        "  'minutes', count(*), a.source_id, a.player_id::text || ':' || m.season_id::text, %s"
        " from player_match_appearances a join matches m on m.id = a.match_id"
        " where m.season_id = %s and a.source_id = %s"
        " group by a.player_id, m.season_id, a.team_id, a.source_id"
        " on conflict (player_id, season_id, team_id, source_id) do update set"
        "  role_key = excluded.role_key, exposure = excluded.exposure, appearances = excluded.appearances,"
        "  ingestion_run_id = excluded.ingestion_run_id, ingested_at = now()",
        (run_id, season_id, SOURCE_ID),
    )
    cur.execute(
        "insert into player_season_metric_values (season_stats_id, metric_key, value)"
        " select s.id, v.metric_key, sum(v.value)"
        " from player_season_stats s"
        " join player_match_appearances a on a.player_id = s.player_id and a.team_id = s.team_id and a.source_id = s.source_id"
        " join matches m on m.id = a.match_id and m.season_id = s.season_id"
        " join player_metric_values v on v.appearance_id = a.id"
        " where s.season_id = %s and s.source_id = %s"
        " group by s.id, v.metric_key"
        " on conflict (season_stats_id, metric_key) do update set value = excluded.value",
        (season_id, SOURCE_ID),
    )


def load_competition_season(
    conn: psycopg.Connection,
    competition_id: int,
    season_id: int,
    fetch: Fetch = fetch_json,
) -> Any:
    """Loads every match of a competition-season. Each match commits on its own, so a
    failure part-way keeps the matches already loaded and marks the run as failed.
    Returns the ingestion run ID."""
    meta = next(
        (
            c for c in fetch("competitions.json")
            if c["competition_id"] == competition_id and c["season_id"] == season_id
        ),
        None,
    )
    if meta is None:
        raise ValueError(f"StatsBomb open data has no competition {competition_id} season {season_id}")

    with conn.cursor() as cur:
        cur.execute(
            "insert into ingestion_runs (source_id, notes) values (%s, %s) returning id",
            (SOURCE_ID, f'{meta["competition_name"]} {meta["season_name"]}'),
        )
        run_id = cur.fetchone()[0]
    conn.commit()

    loaded = 0
    try:
        with conn.cursor() as cur:
            db_competition_id = _upsert_competition(cur, meta)
            db_season_id = _upsert_season(cur, db_competition_id, meta)
        conn.commit()
        for match in fetch(f"matches/{competition_id}/{season_id}.json"):
            events = fetch(f'events/{match["match_id"]}.json')
            with conn.cursor() as cur:
                loaded += _load_match(cur, run_id, db_season_id, match, events)
                cur.execute("update ingestion_runs set records_ingested = %s where id = %s", (loaded, run_id))
            conn.commit()
    except BaseException as error:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "update ingestion_runs set status = 'failed', finished_at = now(), notes = notes || %s"
                " where id = %s",
                (f" | failed: {error!r}", run_id),
            )
        conn.commit()
        raise

    with conn.cursor() as cur:
        _refresh_season_stats(cur, run_id, db_season_id)
        cur.execute(
            "update ingestion_runs set status = 'succeeded', finished_at = now() where id = %s",
            (run_id,),
        )
    conn.commit()
    return run_id
