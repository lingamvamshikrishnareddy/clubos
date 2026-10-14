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
    "match_events, player_season_metric_values, player_season_stats, player_metric_values, player_match_appearances, player_identities, players, "
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
        for table in ("competitions", "seasons", "teams", "matches", "players", "player_identities",
                      "player_match_appearances", "player_metric_values", "player_season_stats",
                      "player_season_metric_values")
    }


def test_loads_competition_season(conn):
    run_id = load_competition_season(conn, 1, 2, fetch=FILES.__getitem__)

    assert counts(conn) == {
        "competitions": 1, "seasons": 1, "teams": 2, "matches": 1, "players": 2,
        "player_identities": 2, "player_match_appearances": 2, "player_metric_values": 28,
        "player_season_stats": 2, "player_season_metric_values": 28,
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


def test_rolls_up_season_stats(conn):
    load_competition_season(conn, 1, 2, fetch=FILES.__getitem__)
    rows = conn.execute(
        "select i.external_id, s.role_key, s.exposure, s.exposure_unit, s.appearances, v.value"
        " from player_season_stats s join player_identities i on i.player_id = s.player_id"
        " join player_season_metric_values v on v.season_stats_id = s.id and v.metric_key = 'shots'"
        " order by i.external_id"
    ).fetchall()
    assert rows == [("10", "striker", 60, "minutes", 1, 2), ("8", "central_midfielder", 90, "minutes", 1, 0)]


def test_stores_passes_and_shots_for_networks(conn):
    load_competition_season(conn, 1, 2, fetch=FILES.__getitem__)
    assert conn.execute(
        "select event_type, count(*) from match_events group by 1 order by 1").fetchall() == [("pass", 3), ("shot", 2)]
    # Only the completed pass with a known recipient forms a network edge.
    edge = conn.execute(
        "select pa.full_name, pr.full_name, n.passes from v_passing_network n"
        " join players pa on pa.id = n.passer_id join players pr on pr.id = n.receiver_id").fetchall()
    assert edge == [("Test Midfielder", "Test Striker", 1)]
    assert scalar(conn, "select x from match_events where source_record_id = 'p1'") == 50


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


def test_knockouts_stay_out_of_tables_and_groups_are_recorded(empty_db):
    group_match = {**MATCH, "competition_stage": {"name": "Group Stage"},
                   "home_team": {**MATCH["home_team"], "home_team_group": "F"},
                   "away_team": {**MATCH["away_team"], "away_team_group": "F"}}
    final = {**MATCH, "match_id": 124, "match_date": "2025-12-18", "competition_stage": {"name": "Final"},
             "home_score": 3, "away_score": 3}
    files = {**FILES, "matches/1/2.json": [group_match, final], "events/124.json": EVENTS}
    conn = empty_db
    load_competition_season(conn, 1, 2, fetch=files.__getitem__)
    assert dict(conn.execute("select stage, count(*) from matches group by 1").fetchall()) == {"regular": 1, "final": 1}
    table = conn.execute("select team, played, points, group_name, group_position from v_league_table order by position").fetchall()
    assert table == [("Riverside FC", 1, 3, "2025/26 Group F", 1), ("Hillcrest United", 1, 0, "2025/26 Group F", 2)]


def test_reference_league_absorbs_an_earlier_statsbomb_competition(empty_db):
    from clubos_ingest.leagues import load_leagues

    conn = empty_db
    premier = [{**COMPETITIONS[0], "competition_id": 2, "season_id": 27, "competition_name": "Premier League",
                "season_name": "2015/2016"}]
    files = {"competitions.json": premier, "matches/2/27.json": [MATCH], "events/123.json": EVENTS}
    load_competition_season(conn, 2, 27, fetch=files.__getitem__)  # before the reference league exists
    ids = load_leagues(conn, ["premier_league"])
    one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    assert one("select count(*) from competitions where sport_id = 'soccer'") == 1
    assert one("select count(*) from seasons where competition_id = (select id from competitions where reference_key = 'premier_league')") == 1
    load_competition_season(conn, 2, 27, fetch=files.__getitem__)  # reload goes into the reference league
    assert one("select count(*) from competitions where sport_id = 'soccer'") == 1
    assert ids["premier_league"] == one("select id from competitions where reference_key = 'premier_league'")
