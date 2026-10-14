"""Aggregate StatsBomb open-data events into per-player match stats.

Data source: https://github.com/statsbomb/open-data. Its licence requires attribution
and does not allow redistribution as our own data, so raw files are never committed.
They are fetched at ingest time (see cli.py).

Metric keys must match packages/sports/soccer/metrics.json.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SOURCE_ID = "statsbomb_open_data"

# StatsBomb pitch is 120 x 80 with the attacking goal at x = 120.
GOAL_CENTRE = (120.0, 40.0)
DEFENSIVE_ZONE_END_X = 48.0  # Defensive 40% of the pitch.
PROGRESSION_RATIO = 0.75  # End at least 25% closer to goal.

# Period 5 is a penalty shoot-out: not part of the match for stats or minutes.
SHOOTOUT_PERIOD = 5

SUCCESS_OUTCOMES = {"Won", "Success", "Success In Play", "Success Out"}

METRIC_KEYS = (
    "goals",
    "np_xg",
    "shots",
    "xa",
    "key_passes",
    "passes_attempted",
    "passes_completed",
    "progressive_passes",
    "progressive_carries",
    "dribbles_completed",
    "pressures",
    "tackles_won",
    "interceptions",
    "ball_recoveries",
)


@dataclass
class PlayerMatchStats:
    source_player_id: str
    player_name: str
    source_team_id: str
    team_name: str
    # Most frequent StatsBomb position in the match.
    position: str | None
    minutes: float | None
    metrics: dict[str, float] = field(default_factory=lambda: dict.fromkeys(METRIC_KEYS, 0.0))
    # Provenance (ADR-0002)
    source_id: str = SOURCE_ID
    source_match_id: str = ""
    ingested_at: str = ""


def _distance_to_goal(point: list[float]) -> float:
    return math.dist(point[:2], GOAL_CENTRE)


def is_progressive(start: list[float] | None, end: list[float] | None) -> bool:
    if not start or not end or start[0] < DEFENSIVE_ZONE_END_X:
        return False
    return _distance_to_goal(end) <= PROGRESSION_RATIO * _distance_to_goal(start)


def _minute(event: dict[str, Any]) -> float:
    return event["minute"] + event.get("second", 0) / 60


def _minutes_played(events: list[dict[str, Any]]) -> dict[str, float]:
    """Minutes per player from starting line-ups and substitutions.

    Red cards and injuries without a substitution are not yet accounted for, so such
    players are credited until full time.
    """
    match_end = max((_minute(e) for e in events), default=0.0)
    on_at: dict[str, float] = {}
    off_at: dict[str, float] = {}
    for event in events:
        kind = event["type"]["name"]
        if kind == "Starting XI":
            for slot in event["tactics"]["lineup"]:
                on_at[str(slot["player"]["id"])] = 0.0
        elif kind == "Substitution":
            off_at[str(event["player"]["id"])] = _minute(event)
            on_at[str(event["substitution"]["replacement"]["id"])] = _minute(event)
    return {
        pid: round(off_at.get(pid, match_end) - start, 1) for pid, start in on_at.items()
    }


def aggregate_match(
    match_id: str | int,
    events: list[dict[str, Any]],
    ingested_at: datetime | None = None,
) -> list[PlayerMatchStats]:
    ingested = (ingested_at or datetime.now(timezone.utc)).isoformat()
    events = [e for e in events if e.get("period", 1) != SHOOTOUT_PERIOD]
    minutes = _minutes_played(events)
    shot_xg = {
        e["id"]: e["shot"].get("statsbomb_xg", 0.0)
        for e in events
        if e["type"]["name"] == "Shot"
    }
    players: dict[str, PlayerMatchStats] = {}
    positions: dict[str, Counter[str]] = {}

    def stats_for(event: dict[str, Any]) -> PlayerMatchStats:
        pid = str(event["player"]["id"])
        if pid not in players:
            players[pid] = PlayerMatchStats(
                source_player_id=pid,
                player_name=event["player"]["name"],
                source_team_id=str(event["team"]["id"]),
                team_name=event["team"]["name"],
                position=None,
                minutes=minutes.get(pid),
                source_match_id=str(match_id),
                ingested_at=ingested,
            )
        return players[pid]

    for event in events:
        if "player" not in event:
            continue
        # Unused substitutes still appear in events (e.g. booked on the bench). When
        # line-ups are known, only players who were on the pitch get an appearance.
        if minutes and str(event["player"]["id"]) not in minutes:
            continue
        kind = event["type"]["name"]
        m = stats_for(event).metrics
        if position := event.get("position", {}).get("name"):
            positions.setdefault(str(event["player"]["id"]), Counter())[position] += 1

        if kind == "Shot":
            shot = event["shot"]
            m["shots"] += 1
            if shot.get("outcome", {}).get("name") == "Goal":
                m["goals"] += 1
            if shot.get("type", {}).get("name") != "Penalty":
                m["np_xg"] += shot.get("statsbomb_xg", 0.0)
        elif kind == "Pass":
            p = event["pass"]
            m["passes_attempted"] += 1
            completed = "outcome" not in p  # StatsBomb omits outcome for completed passes.
            if completed:
                m["passes_completed"] += 1
                if is_progressive(event.get("location"), p.get("end_location")):
                    m["progressive_passes"] += 1
            if p.get("shot_assist") or p.get("goal_assist"):
                m["key_passes"] += 1
                m["xa"] += shot_xg.get(p.get("assisted_shot_id"), 0.0)
        elif kind == "Carry":
            if is_progressive(event.get("location"), event["carry"].get("end_location")):
                m["progressive_carries"] += 1
        elif kind == "Dribble":
            if event["dribble"].get("outcome", {}).get("name") == "Complete":
                m["dribbles_completed"] += 1
        elif kind == "Pressure":
            m["pressures"] += 1
        elif kind == "Duel":
            duel = event["duel"]
            if (
                duel.get("type", {}).get("name") == "Tackle"
                and duel.get("outcome", {}).get("name") in SUCCESS_OUTCOMES
            ):
                m["tackles_won"] += 1
        elif kind == "Interception":
            if event["interception"].get("outcome", {}).get("name") in SUCCESS_OUTCOMES:
                m["interceptions"] += 1
        elif kind == "Ball Recovery":
            if not event.get("ball_recovery", {}).get("recovery_failure"):
                m["ball_recoveries"] += 1

    for pid, counts in positions.items():
        players[pid].position = counts.most_common(1)[0][0]
    return list(players.values())


# StatsBomb position name -> soccer role key (packages/sports/soccer/roles.json).
POSITION_ROLES = {
    "Goalkeeper": "goalkeeper",
    "Center Back": "centre_back",
    "Left Center Back": "centre_back",
    "Right Center Back": "centre_back",
    "Left Back": "full_back",
    "Right Back": "full_back",
    "Left Wing Back": "full_back",
    "Right Wing Back": "full_back",
    "Center Defensive Midfield": "defensive_midfielder",
    "Left Defensive Midfield": "defensive_midfielder",
    "Right Defensive Midfield": "defensive_midfielder",
    "Center Midfield": "central_midfielder",
    "Left Center Midfield": "central_midfielder",
    "Right Center Midfield": "central_midfielder",
    "Center Attacking Midfield": "attacking_midfielder",
    "Left Attacking Midfield": "attacking_midfielder",
    "Right Attacking Midfield": "attacking_midfielder",
    "Left Midfield": "winger",
    "Right Midfield": "winger",
    "Left Wing": "winger",
    "Right Wing": "winger",
    "Center Forward": "striker",
    "Left Center Forward": "striker",
    "Right Center Forward": "striker",
    "Secondary Striker": "striker",
}


def role_for_position(position: str | None) -> str | None:
    """Unknown or missing positions stay unknown rather than being guessed."""
    return POSITION_ROLES.get(position) if position else None
