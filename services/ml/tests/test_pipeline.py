"""Runs every model job on fictional demo data in Postgres.

Set CLUBOS_TEST_DATABASE_URL (a database with db/migrations applied) to run.
"""

import os
from datetime import date

import pytest

psycopg = pytest.importorskip("psycopg")
from clubos_ingest.mock import load_mock_data  # noqa: E402
from clubos_ml.pipeline import run_all  # noqa: E402

DATABASE_URL = os.environ.get("CLUBOS_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="CLUBOS_TEST_DATABASE_URL not set")
AS_OF = date(2026, 10, 14)


@pytest.fixture(scope="module")
def conn():
    with psycopg.connect(DATABASE_URL) as connection:
        tables = [r[0] for r in connection.execute(
            "select tablename from pg_tables where schemaname = 'public' and tablename not in ('sports', 'data_sources')")]
        connection.execute(f"truncate {', '.join(tables)} cascade")
        connection.commit()
        load_mock_data(connection, ["soccer", "ice_hockey", "basketball"], seed=5, as_of=AS_OF)
        connection.summary = run_all(connection, AS_OF)
        yield connection
        connection.rollback()
        connection.execute(f"truncate {', '.join(tables)} cascade")
        connection.commit()


def one(conn, sql, *params):
    return conn.execute(sql, params).fetchone()[0]


def test_every_job_produced_output(conn):
    assert all(count > 0 for count in conn.summary.values()), conn.summary


def test_valuations_have_ranges_and_a_model_card(conn):
    assert one(conn, "select count(*) from player_valuations where not (value_low <= value and value <= value_high)") == 0
    card = one(conn, "select card from model_runs where model_name = 'valuation_baseline' and sport_id = 'soccer'")
    assert card["basis"] == "transfer_fee" and card["limitations"]
    assert one(conn, "select distinct basis from player_valuations v join players p on p.id = v.player_id"
                     " where p.sport_id = 'ice_hockey'") == "annual_salary"


def test_recommendations_exclude_own_squad_and_explain_themselves(conn):
    assert one(conn, "select count(*) from recommendations r join squad_members s"
                     " on s.player_id = r.player_id and s.organisation_id = r.organisation_id") == 0
    assert one(conn, "select max(c) from (select count(*) c from recommendations group by style_profile_id) t") <= 10
    assert one(conn, "select count(*) from recommendations where jsonb_array_length(reasons) = 0") == 0


def test_forecasts_are_bounded(conn):
    assert one(conn, "select count(*) from performance_forecasts"
                     " where not (forecast_low <= forecast and forecast <= forecast_high)") == 0
    assert one(conn, "select count(*) from performance_forecasts where evidence_weight not between 0 and 1") == 0


def test_workload_indicators_flag_the_overloaded_players(conn):
    assert one(conn, "select count(*) from workload_indicators where 'load_spike' = any(flags)") > 0


def test_unit_combinations_cover_lineups_lines_and_pairs(conn):
    kinds = dict(conn.execute("select unit_kind, min(cardinality(player_ids)) from unit_stats group by 1").fetchall())
    assert kinds == {"lineup": 5, "forward_line": 3, "defence_pair": 2}
    # Lineup points for and against add up to the points scored in the simulated games.
    lineup_points = one(conn, "select sum(value_for) from unit_stats where unit_kind = 'lineup'")
    event_points = one(conn, "select sum(e.value) from match_events e join players p on p.id = e.player_id"
                             " where p.sport_id = 'basketball' and e.event_type in ('shot', 'free_throw') and e.period <= 4")
    assert lineup_points == event_points


def test_formations_detected_from_the_demo_shape(conn):
    assert one(conn, "select count(*) from formation_detections where formation <> '4-2-3-1'") == 0


def test_financial_forecast_uses_contracts_for_wages(conn):
    row = conn.execute(
        "select basis, actual_to_date + projected_remaining - projected_full_year from financial_forecasts"
        " where category = 'player_wages' limit 1").fetchone()
    assert row[0] == "contracted" and abs(row[1]) < 1
    plan_years = one(conn, "select count(distinct fiscal_year) from financial_plan_lines")
    assert plan_years == 3
    # Costs are negative in the plan, income positive.
    assert one(conn, "select count(*) from financial_plan_lines where category = 'player_wages' and amount >= 0") == 0


def test_performance_roi_views(conn):
    assert one(conn, "select count(*) from v_club_performance_roi") == 6  # three clubs, two seasons
    assert one(conn, "select count(*) from v_player_performance_roi where performance_score is not null") > 0


def test_player_reports_cite_their_sources(conn):
    sections = one(conn, "select sections from player_reports limit 1")
    assert sections and all(item.get("source") for section in sections for item in section["items"])
