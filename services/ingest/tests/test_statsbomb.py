import json
from pathlib import Path

import pytest

from clubos_ingest.statsbomb import METRIC_KEYS, POSITION_ROLES, aggregate_match, is_progressive, role_for_position

SOCCER = json.loads((Path(__file__).parents[3] / "packages/sports/soccer/sport.json").read_text())

HOME = {"id": 1, "name": "Riverside FC"}
STRIKER = {"id": 10, "name": "Test Striker"}
MIDFIELDER = {"id": 8, "name": "Test Midfielder"}
SUB = {"id": 20, "name": "Test Substitute"}
BENCH = {"id": 30, "name": "Test Bench Player"}


def ev(id_, minute, type_name, player=None, **extra):
    event = {"id": id_, "minute": minute, "second": 0, "type": {"name": type_name}, "team": HOME}
    if player:
        event["player"] = player
        event["position"] = {"name": "Center Forward" if player is STRIKER else "Center Midfield"}
    event.update(extra)
    return event


EVENTS = [
    ev("xi", 0, "Starting XI", tactics={"lineup": [{"player": STRIKER}, {"player": MIDFIELDER}]}),
    # Completed progressive pass that assists a shot.
    ev("p1", 10, "Pass", MIDFIELDER, location=[60, 40], **{
        "pass": {"end_location": [100, 40], "shot_assist": True, "assisted_shot_id": "s1"}
    }),
    ev("s1", 10, "Shot", STRIKER, shot={"statsbomb_xg": 0.3, "outcome": {"name": "Goal"}}),
    # Incomplete pass: attempted, not completed, not progressive.
    ev("p2", 20, "Pass", MIDFIELDER, location=[60, 40], **{
        "pass": {"end_location": [110, 40], "outcome": {"name": "Incomplete"}}
    }),
    # Pass from the defensive 40% is never progressive.
    ev("p3", 25, "Pass", MIDFIELDER, location=[30, 40], **{"pass": {"end_location": [90, 40]}}),
    ev("s2", 30, "Shot", STRIKER, shot={"statsbomb_xg": 0.76, "type": {"name": "Penalty"}, "outcome": {"name": "Goal"}}),
    ev("c1", 35, "Carry", MIDFIELDER, location=[50, 40], carry={"end_location": [90, 40]}),
    ev("d1", 40, "Dribble", STRIKER, dribble={"outcome": {"name": "Complete"}}),
    ev("d2", 41, "Dribble", STRIKER, dribble={"outcome": {"name": "Incomplete"}}),
    ev("pr", 50, "Pressure", STRIKER),
    ev("t1", 55, "Duel", MIDFIELDER, duel={"type": {"name": "Tackle"}, "outcome": {"name": "Won"}}),
    ev("t2", 56, "Duel", MIDFIELDER, duel={"type": {"name": "Tackle"}, "outcome": {"name": "Lost In Play"}}),
    ev("i1", 57, "Interception", MIDFIELDER, interception={"outcome": {"name": "Success In Play"}}),
    ev("r1", 58, "Ball Recovery", MIDFIELDER),
    ev("r2", 59, "Ball Recovery", MIDFIELDER, ball_recovery={"recovery_failure": True}),
    ev("sub", 60, "Substitution", STRIKER, substitution={"replacement": SUB}),
    # Booked on the bench: never played.
    ev("bb", 70, "Bad Behaviour", BENCH),
    ev("end", 90, "Half End"),
    # Penalty shoot-out: excluded from stats and minutes.
    ev("so", 125, "Shot", STRIKER, period=5, shot={"statsbomb_xg": 0.78, "type": {"name": "Penalty"}, "outcome": {"name": "Goal"}}),
]


@pytest.fixture(scope="module")
def stats():
    return {row.source_player_id: row for row in aggregate_match(123, EVENTS)}


def test_metric_keys_match_shared_definitions():
    shared = {m["key"] for m in SOCCER["metrics"]}
    assert set(METRIC_KEYS) == shared


def test_minutes_from_lineups_and_substitutions(stats):
    assert stats["10"].minutes == 60
    assert stats["8"].minutes == 90  # Shoot-out does not extend the match.


def test_players_who_never_played_have_no_row(stats):
    assert "30" not in stats


def test_striker_metrics(stats):
    m = stats["10"].metrics
    assert m["shots"] == 2
    assert m["goals"] == 2
    assert m["np_xg"] == pytest.approx(0.3)  # Penalty xG excluded.
    assert m["dribbles_completed"] == 1
    assert m["pressures"] == 1


def test_midfielder_metrics(stats):
    m = stats["8"].metrics
    assert m["passes_attempted"] == 3
    assert m["passes_completed"] == 2
    assert m["progressive_passes"] == 1
    assert m["key_passes"] == 1
    assert m["xa"] == pytest.approx(0.3)
    assert m["progressive_carries"] == 1
    assert m["tackles_won"] == 1
    assert m["interceptions"] == 1
    assert m["ball_recoveries"] == 1


def test_provenance(stats):
    row = stats["10"]
    assert row.source_id == "statsbomb_open_data"
    assert row.source_match_id == "123"
    assert row.ingested_at


def test_is_progressive_requires_start_location():
    assert not is_progressive(None, [100, 40])


def test_position_roles_use_shared_role_keys():
    roles = {r["key"] for r in SOCCER["roles"]}
    assert set(POSITION_ROLES.values()) <= roles


def test_unknown_position_stays_unknown():
    assert role_for_position("Sweeper Keeper") is None
    assert role_for_position(None) is None


def test_team_and_most_frequent_position(stats):
    assert stats["10"].source_team_id == "1"
    assert stats["10"].position == "Center Forward"
