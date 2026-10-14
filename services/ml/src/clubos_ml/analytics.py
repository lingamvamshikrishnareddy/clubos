"""Sport analytics from play-by-play: unit combinations (lineups, lines, pairs) and
formation detection. What to compute comes from each sport's sport.json (units,
formation), so this code does not branch on sport."""

from __future__ import annotations

import bisect
from collections import defaultdict
from typing import Any

import numpy as np
import psycopg
from psycopg.types.json import Jsonb

from .pipeline import create_model_run


def time_slices(shifts: list[tuple[Any, float, float]]) -> list[tuple[float, float, frozenset]]:
    """Splits overlapping shifts [(player, start, end)] into slices with a constant set of
    players on the field: [(start, end, players)]."""
    bounds = sorted({t for _, start, end in shifts for t in (start, end)})
    slices = []
    for a, b in zip(bounds, bounds[1:]):
        on = frozenset(p for p, start, end in shifts if start <= a and end >= b)
        if on:
            slices.append((a, b, on))
    return slices


def run_units(conn: psycopg.Connection, sport: dict[str, Any]) -> int:
    units = sport.get("units") or []
    if not units:
        return 0
    group_of = {r["key"]: r["group"] for r in sport["roles"]}
    run_id = create_model_run(
        conn, "unit_combinations", "0.1.0", sport["id"],
        {"intended_use": "How player combinations perform while on together.",
         "method": "Shifts are split into time slices with a constant set of players; each unit's time on, and "
                   "the value of events for and against while it was on, are summed per team and season.",
         "limitations": ["Small samples: units with little time together are noisy.", "No opponent-quality adjustment."]},
        {},
    )
    shifts = conn.execute(
        """
        select ps.match_id, m.season_id, ps.team_id, ps.period, ps.player_id, p.primary_role, ps.start_seconds, ps.end_seconds
        from player_shifts ps join players p on p.id = ps.player_id join matches m on m.id = ps.match_id
        where p.sport_id = %s
        """, (sport["id"],)).fetchall()
    by_key: dict[tuple, list[tuple[Any, float, float]]] = defaultdict(list)
    role_of: dict[Any, str] = {}
    season_of: dict[Any, Any] = {}
    for match_id, season_id, team_id, period, player_id, role, start, end in shifts:
        by_key[(match_id, team_id, period)].append((player_id, float(start), float(end)))
        role_of[player_id] = role
        season_of[match_id] = season_id
    if not by_key:
        return 0

    value_events = {e for u in units for e in u["valueEvents"]}
    events = conn.execute(
        "select e.match_id, e.team_id, e.period, e.clock_seconds, e.event_type, coalesce(e.value, 0)"
        " from match_events e where e.match_id = any(%s) and e.event_type = any(%s) and e.clock_seconds is not null",
        (list(season_of), list(value_events))).fetchall()

    slices = {key: time_slices(s) for key, s in by_key.items()}
    teams_in_match: dict[Any, set] = defaultdict(set)
    for match_id, team_id, _ in by_key:
        teams_in_match[match_id].add(team_id)

    def unit_members(on: frozenset, unit: dict[str, Any]) -> frozenset | None:
        members = frozenset(p for p in on if group_of.get(role_of[p]) in unit["groups"])
        return members if len(members) == unit["size"] else None

    totals: dict[tuple, dict[str, Any]] = {}

    def entry(team_id: Any, season_id: Any, kind: str, members: frozenset) -> dict[str, Any]:
        return totals.setdefault((team_id, season_id, kind, members),
                                 {"seconds": 0.0, "for": 0.0, "against": 0.0, "matches": set()})

    for (match_id, team_id, period), team_slices in slices.items():
        for unit in units:
            for a, b, on in team_slices:
                members = unit_members(on, unit)
                if members:
                    e = entry(team_id, season_of[match_id], unit["kind"], members)
                    e["seconds"] += b - a
                    e["matches"].add(match_id)

    for match_id, team_id, period, clock, event_type, value in events:
        clock = float(clock)
        for unit in units:
            if event_type not in unit["valueEvents"]:
                continue
            for side in teams_in_match[match_id]:
                team_slices = slices.get((match_id, side, period), [])
                index = bisect.bisect_right([s[0] for s in team_slices], clock) - 1
                if index < 0 or not (team_slices[index][0] <= clock <= team_slices[index][1]):
                    continue
                members = unit_members(team_slices[index][2], unit)
                if members:
                    e = entry(side, season_of[match_id], unit["kind"], members)
                    e["for" if side == team_id else "against"] += float(value)

    rows = [(run_id, team_id, season_id, kind, list(members), round(e["seconds"], 1), round(e["for"], 3),
             round(e["against"], 3), next(u["valueKind"] for u in units if u["kind"] == kind), len(e["matches"]))
            for (team_id, season_id, kind, members), e in totals.items() if e["seconds"] > 0]
    with conn.cursor() as cur:
        cur.executemany(
            "insert into unit_stats (model_run_id, team_id, season_id, unit_kind, player_ids, seconds_together,"
            " value_for, value_against, value_kind, matches) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", rows)
    return len(rows)


def detect_lines(xs: list[float], formations: list[str]) -> tuple[str, float]:
    """Groups outfield players into lines by depth (x) and returns the closest formation from
    the vocabulary, with a confidence from how cleanly the players separate into lines."""
    values = np.sort(np.array(xs, dtype=float))
    total_var = float(((values - values.mean()) ** 2).sum()) or 1.0
    best: tuple[float, str, float] | None = None
    for formation in formations:
        counts = [int(c) for c in formation.split("-")]
        if sum(counts) != len(values):
            continue
        groups = np.split(values, np.cumsum(counts)[:-1])
        within = float(sum(((g - g.mean()) ** 2).sum() for g in groups))
        # Fewer lines always fit worse, so penalise extra lines slightly.
        score = within / total_var + 0.02 * len(counts)
        if best is None or score < best[0]:
            best = (score, formation, max(0.0, 1 - within / total_var))
    if best is None:
        return "unknown", 0.0
    return best[1], round(best[2], 3)


def run_formations(conn: psycopg.Connection, sport: dict[str, Any]) -> int:
    config = sport.get("formation")
    if not config:
        return 0
    vocab = next(t["values"] for t in sport["videoTags"] if t["key"] == config["tagGroup"])
    excluded_roles = [r["key"] for r in sport["roles"] if r["group"] in config["excludeGroups"]]
    run_id = create_model_run(
        conn, "formation_detection", "0.1.0", sport["id"],
        {"intended_use": "The shape a team took in possession, from where its players were on the ball. "
                         "Not the defensive or starting formation: full-backs pushing on often turn a back four into a three.",
         "method": f"Average positions of the {config['outfieldPlayers']} most involved outfield players are split "
                   "into lines by depth; the formation from the vocabulary with the tightest lines wins.",
         "limitations": ["Uses on-ball events only, so shape without the ball is not captured.",
                         "One shape per match; in-game changes are averaged."]},
        {},
    )
    positions = conn.execute(
        """
        select a.match_id, a.team_id, a.player_id, a.avg_x, a.avg_y, a.events
        from v_average_positions a join players p on p.id = a.player_id
        where p.sport_id = %s and coalesce(p.primary_role, '') <> all(%s)
        order by a.match_id, a.team_id, a.events desc
        """, (sport["id"], excluded_roles)).fetchall()
    grouped: dict[tuple, list] = defaultdict(list)
    for match_id, team_id, player_id, x, y, n in positions:
        if team_id is not None:
            grouped[(match_id, team_id)].append((player_id, float(x), float(y), n))
    written = 0
    for (match_id, team_id), players in grouped.items():
        players = players[: config["outfieldPlayers"]]
        if len(players) < config["outfieldPlayers"]:
            continue
        formation, confidence = detect_lines([p[1] for p in players], list(vocab))
        conn.execute(
            "insert into formation_detections (match_id, team_id, model_run_id, formation, average_positions, confidence)"
            " values (%s, %s, %s, %s, %s, %s)",
            (match_id, team_id, run_id, formation,
             Jsonb([{"player_id": str(p[0]), "x": p[1], "y": p[2]} for p in players]), confidence))
        written += 1
    return written
