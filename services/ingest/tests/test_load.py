"""Integration tests against a Postgres database with db/migrations applied.

Set CLUBOS_TEST_DATABASE_URL to run them. The tests truncate the tables they use.
"""

import os

import pytest

from test_statsbomb import EVENTS

psycopg = pytest.importorskip("psycopg")
from clubos_ingest.load import load_competition_season  # noqa: E402

DATABASE_URL = os.environ.get("CLUBOS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="CLUBOS_TEST_DATABASE_URL not set")

COMPETITIONS = [
    {
        "competition_id": 1, "season_id": 2, "competition_name": "Test League",
        "country_name": "Testland", "competition_gender": "male", "competition_youth": False,
        "season_name": "2025/26",
    }
]
MATCH = {
    "match_id": 123, "match_date": "2025-08-16", "kick_off": "15:00:00.000",
    "home_team": {"home_team_id": 1, "home_team_name": "Riverside FC", "country": {"name": "Testland"}},
    "away_team": {"away_team_id": 2, "away_team_name": "Hillcrest United", "country": {"name": "Testland"}},
    "home_score": 2, "away_score": 0,
}
FILES = {
    "competitions.json": COMPETITIONS,
    "matches/1/2.json": [MATCH],
    "events/123.json": EVENTS,
}

TABLES = (
    "player_metric_values, player_match_appearances, player_identities, players, "
    "matches, seasons, competitions, teams, source_entity_ids, ingestion_runs"
)


@pytest.fixture
def conn():
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(f"truncate {TABLES} cascade")
        connection.commit()
        yield connection
        connection.rollback()
        connection.execute(f"truncate {TABLES} cascade")
        connection.commit()


def scalar(conn, sql, *params):
    return conn.execute(sql, params).fetchone()[0]


def counts(conn):
    return {
        table: scalar(conn, f"select count(*) from {table}")
        for table in ("competitions", "seasons", "teams", "matches", "players",
                      "player_identities", "player_match_appearances", "player_metric_values")
    }


def test_loads_competition_season(conn):
    run_id = load_competition_season(conn, 1, 2, fetch=FILES.__getitem__)

    assert counts(conn) == {
        "competitions": 1, "seasons": 1, "teams": 2, "matches": 1, "players": 2,
        "player_identities": 2, "player_match_appearances": 2, "player_metric_values": 28,
    }
    assert scalar(conn, "select gender from competitions") == "men"
    assert conn.execute("select status, records_ingested from ingestion_runs where id = %s", (run_id,)).fetchone() == (
        "succeeded", 2,
    )

    striker = conn.execute(
        "select p.full_name, p.primary_role, a.role_key, a.minutes, t.name, a.source_record_id, a.ingestion_run_id"
        " from player_identities i join players p on p.id = i.player_id"
        " join player_match_appearances a on a.player_id = p.id join teams t on t.id = a.team_id"
        " where i.source_id = 'statsbomb_open_data' and i.external_id = '10'"
    ).fetchone()
    assert striker == ("Test Striker", "striker", "striker", 60, "Riverside FC", "123:10", run_id)

    assert scalar(
        conn,
        "select v.value from player_metric_values v join player_match_appearances a on a.id = v.appearance_id"
        " join player_identities i on i.player_id = a.player_id"
        " where i.external_id = '8' and v.metric_key = 'progressive_passes'",
    ) == 1


def test_reloading_is_idempotent(conn):
    load_competition_season(conn, 1, 2, fetch=FILES.__getitem__)
    before = counts(conn)
    second_run = load_competition_season(conn, 1, 2, fetch=FILES.__getitem__)

    assert counts(conn) == before
    assert scalar(conn, "select count(*) from ingestion_runs where status = 'succeeded'") == 2
    assert scalar(conn, "select count(distinct ingestion_run_id) from player_match_appearances") == 1
    assert scalar(conn, "select min(ingestion_run_id::text) from player_match_appearances") == str(second_run)


def test_failed_fetch_marks_run_failed(conn):
    def fetch(path):
        if path.startswith("events/"):
            raise ConnectionError("network down")
        return FILES[path]

    with pytest.raises(ConnectionError):
        load_competition_season(conn, 1, 2, fetch=fetch)

    status, notes = conn.execute("select status, notes from ingestion_runs").fetchone()
    assert status == "failed"
    assert "network down" in notes
    assert scalar(conn, "select count(*) from player_match_appearances") == 0


def test_unknown_competition_season(conn):
    with pytest.raises(ValueError):
        load_competition_season(conn, 99, 99, fetch=FILES.__getitem__)
    assert scalar(conn, "select count(*) from ingestion_runs") == 0
