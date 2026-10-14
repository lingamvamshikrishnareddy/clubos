import os
from datetime import date

import pytest

from clubos_ingest.mock import generate, load_mock_data, load_sport
from clubos_ingest.mock_config import LEAGUES

AS_OF = date(2026, 10, 14)


def test_same_seed_same_data():
    a = generate(["soccer"], seed=3, as_of=AS_OF)
    b = generate(["soccer"], seed=3, as_of=AS_OF)
    assert {t: len(r) for t, r in a.tables.items()} == {t: len(r) for t, r in b.tables.items()}
    assert a.tables["players"][:5] == b.tables["players"][:5]


@pytest.mark.parametrize("sport_id", sorted(LEAGUES))
def test_metrics_follow_the_sport_definition(sport_id):
    sport = load_sport(LEAGUES[sport_id].slug)
    metrics = {m["key"]: m for m in sport["metrics"]}
    rows = generate([sport_id], seed=1, as_of=AS_OF)
    stats = {r["id"]: r for r in rows.tables["player_season_stats"]}
    roles = {r["key"] for r in sport["roles"]}
    for value_row in rows.tables["player_season_metric_values"]:
        stat = stats[value_row["season_stats_id"]]
        assert stat["role_key"] in roles
        assert value_row["metric_key"] in sport["comparisonMetrics"][stat["role_key"]]
        metric = metrics[value_row["metric_key"]]
        if metric["normalisation"] == "rate":
            low, high = metric["typical"]
            assert low <= value_row["value"] <= high, (metric["key"], value_row["value"])


def test_every_sport_has_a_club_and_league():
    rows = generate(seed=1, as_of=AS_OF)
    assert len(rows.tables["organisations"]) == len(LEAGUES) == 6
    assert {c["sport_id"] for c in rows.tables["competitions"]} == set(LEAGUES)
    assert all(r["source_id"] == "mock" for r in rows.tables["player_season_stats"])


DATABASE_URL = os.environ.get("CLUBOS_TEST_DATABASE_URL")


@pytest.mark.skipif(not DATABASE_URL, reason="CLUBOS_TEST_DATABASE_URL not set")
def test_loads_into_postgres_and_refuses_a_second_load():
    psycopg = pytest.importorskip("psycopg")
    with psycopg.connect(DATABASE_URL) as conn:
        tables = [r[0] for r in conn.execute(
            "select tablename from pg_tables where schemaname = 'public' and tablename not in ('sports', 'data_sources')")]
        conn.execute(f"truncate {', '.join(tables)} cascade")
        conn.commit()
        try:
            counts = load_mock_data(conn, ["soccer", "cricket"], seed=2, as_of=AS_OF)
            assert counts["organisations"] == 2
            # Views used for executive reporting return a row per club.
            assert conn.execute("select count(*) from v_wage_bill").fetchone()[0] == 2
            assert conn.execute("select count(*) from v_budget_vs_actual where spent > 0").fetchone()[0] > 0
            with pytest.raises(RuntimeError):
                load_mock_data(conn, ["soccer"], seed=2, as_of=AS_OF)
        finally:
            conn.rollback()
            conn.execute(f"truncate {', '.join(tables)} cascade")
            conn.commit()


@pytest.mark.parametrize("sport_id", sorted(LEAGUES))
def test_play_by_play_uses_the_sport_vocabulary_and_sets_scores(sport_id):
    sport = load_sport(LEAGUES[sport_id].slug)
    event_types = {e["key"] for e in sport["eventTypes"]}
    vocab = {t["key"]: set(t["values"]) for t in sport["videoTags"]}
    rows = generate([sport_id], seed=4, as_of=AS_OF)
    events = rows.tables["match_events"]
    assert events
    for e in events:
        assert e["event_type"] in event_types
        for key, value in e["attributes"].items():
            if key in vocab:
                assert value in vocab[key], (key, value)
    detailed = {e["match_id"] for e in events}
    matches = {m["id"]: m for m in rows.tables["matches"] if m["id"] in detailed}
    assert len(matches) == 3
    for match in matches.values():
        assert match["home_score"] != match["away_score"] or sport_id == "soccer"
