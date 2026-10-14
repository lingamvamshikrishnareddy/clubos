"""Fictional play-by-play for a handful of demo matches, one simulator per sport.

Each simulator writes match_events (and player_shifts where the sport needs them) and
then sets the match score from the simulated events, so scores and events always agree.
Coordinates follow db/migrations/0010: 0–100 on both axes, attacking towards x = 100.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

SOURCE_ID = "mock"


class EventWriter:
    def __init__(self, g: Any, rows: Any, match: dict[str, Any]):
        self.g, self.rows, self.match, self.seq = g, rows, match, 0

    def add(self, period: int, clock: float | None, team_id: Any, player: Any, event_type: str, *,
            outcome: str | None = None, related: Any = None, x: float | None = None, y: float | None = None,
            end_x: float | None = None, end_y: float | None = None, value: float | None = None,
            attributes: dict[str, Any] | None = None) -> None:
        self.seq += 1
        clamp = lambda v: None if v is None else round(min(max(v, 0.0), 100.0), 2)  # noqa: E731
        self.rows.add(
            "match_events", id=self.g.id(), match_id=self.match["id"], source_id=SOURCE_ID,
            source_record_id=f"{self.match['id']}:{self.seq}", sequence=self.seq, period=period,
            clock_seconds=None if clock is None else round(clock, 1), team_id=team_id,
            player_id=player.id if player else None, related_player_id=related.id if related else None,
            event_type=event_type, outcome=outcome, x=clamp(x), y=clamp(y), end_x=clamp(end_x), end_y=clamp(end_y),
            value=None if value is None else round(value, 3), attributes=attributes or {},
        )

    def shift(self, player: Any, team_id: Any, period: int, start: float, end: float) -> None:
        if end > start:
            self.rows.add("player_shifts", match_id=self.match["id"], player_id=player.id, team_id=team_id,
                          period=period, start_seconds=round(start, 1), end_seconds=round(end, 1), source_id=SOURCE_ID)


def lineup(players: list[Any], role: str) -> list[Any]:
    return sorted((p for p in players if p.role == role), key=lambda p: p.depth)


def starters(players: list[Any]) -> list[Any]:
    return [p for p in players if p.starter]


# ---------------------------------------------------------------------------
# Soccer: passes and shots
# ---------------------------------------------------------------------------

SOCCER_SPOTS = {
    "goalkeeper": [(5, 50)], "centre_back": [(22, 38), (22, 62)], "full_back": [(32, 12), (32, 88)],
    "defensive_midfielder": [(40, 50)], "central_midfielder": [(52, 35), (52, 65)],
    "attacking_midfielder": [(66, 50)], "winger": [(72, 10), (72, 90)], "striker": [(84, 50)],
}


def soccer(w: EventWriter, sport: dict, home: tuple[Any, list], away: tuple[Any, list]) -> tuple[int, int]:
    g = w.g
    goals = []
    for team_id, squad in (home, away):
        xi = starters(squad)
        spots = {}
        for role, places in SOCCER_SPOTS.items():
            for p, spot in zip(lineup(xi, role), places):
                spots[p.id] = spot
        xi = [p for p in xi if p.id in spots]
        weights = [0.4 if p.role == "goalkeeper" else 1.6 if p.role.endswith("midfielder") else 1.0 for p in xi]
        for _ in range(g.rng.randint(330, 470)):
            period = 1 if g.chance(0.5) else 2
            passer = g.rng.choices(xi, weights)[0]
            receiver = g.pick([p for p in xi if p is not passer and abs(spots[p.id][0] - spots[passer.id][0]) < 40] or xi)
            sx, sy = spots[passer.id]
            ex, ey = spots[receiver.id]
            complete = g.chance(0.84 if ex <= sx + 10 else 0.68)
            w.add(period, g.between(0, 2700), team_id, passer, "pass", outcome="complete" if complete else "incomplete",
                  related=receiver if complete else None, x=sx + g.rng.gauss(0, 8), y=sy + g.rng.gauss(0, 8),
                  end_x=ex + g.rng.gauss(0, 8), end_y=ey + g.rng.gauss(0, 8))
        shooters = [p for p in xi if p.role in ("striker", "winger", "attacking_midfielder", "central_midfielder")]
        scored = 0
        for _ in range(g.rng.randint(7, 17)):
            shooter = g.rng.choices(shooters, [3 if p.role == "striker" else 1 for p in shooters])[0]
            x, y = g.between(75, 99), g.between(25, 75)
            distance = math.hypot((100 - x) * 1.05, (50 - y) * 0.68)
            xg = min(0.75, 0.6 * math.exp(-distance / 9))
            goal = g.chance(xg)
            scored += goal
            w.add(1 if g.chance(0.5) else 2, g.between(0, 2700), team_id, shooter, "shot",
                  outcome="goal" if goal else g.pick(("saved", "off_target", "blocked")), x=x, y=y, value=xg,
                  attributes={"phase": g.pick(("build-up", "counter-attack", "final third", "set piece"))})
        goals.append(scored)
    return goals[0], goals[1]


# ---------------------------------------------------------------------------
# Basketball: shots, free throws, stints (for lineups)
# ---------------------------------------------------------------------------

BASKETBALL_ZONES = {  # zone: (x range, y range, make probability, points)
    "rim": ((90, 98), (42, 58), 0.63, 2), "short mid-range": ((80, 90), (30, 70), 0.43, 2),
    "long mid-range": ((70, 80), (15, 85), 0.40, 2), "corner three": ((88, 98), (2, 8), 0.39, 3),
    "above-the-break three": ((62, 72), (15, 85), 0.35, 3),
}


def basketball(w: EventWriter, sport: dict, home: tuple[Any, list], away: tuple[Any, list]) -> tuple[int, int]:
    g = w.g
    scores = []
    for team_id, squad in (home, away):
        first = starters(squad)
        bench = sorted((p for p in squad if not p.starter), key=lambda p: (p.depth, p.role))
        segments = []  # (period, start, end, five players)
        for period in range(1, 5):
            subs = first[:2] + bench[:3] if period % 2 else first[2:4] + bench[1:4]
            segments += [(period, 0, 420, first), (period, 420, 600, subs), (period, 600, 720, first)]
        on_court: dict[Any, list[tuple[int, float, float]]] = {}
        for period, start, end, five in segments:
            for p in five:
                on_court.setdefault(p.id, []).append((period, start, end))
                w.shift(p, team_id, period, start, end)
        points = 0
        for _ in range(g.rng.randint(80, 92)):
            period, start, end, five = g.pick(segments)
            shooter = g.rng.choices(five, [1.4 if p.starter else 1 for p in five])[0]
            zone = g.rng.choices(list(BASKETBALL_ZONES), [30, 12, 8, 10, 40])[0]
            (x0, x1), (y0, y1), p_make, value = BASKETBALL_ZONES[zone]
            made = g.chance(p_make)
            assister = g.pick([p for p in five if p is not shooter]) if made and g.chance(0.6) else None
            points += value if made else 0
            w.add(period, g.between(start, end), team_id, shooter, "shot", outcome="made" if made else "missed",
                  related=assister, x=g.between(x0, x1), y=g.between(y0, y1), value=value if made else 0,
                  attributes={"shot_zone": zone, "play_type": g.pick(sport["videoTags"][0]["values"])})
        for _ in range(g.rng.randint(14, 26)):
            period, start, end, five = g.pick(segments)
            made = g.chance(0.77)
            points += made
            w.add(period, g.between(start, end), team_id, g.pick(five), "free_throw",
                  outcome="made" if made else "missed", value=1 if made else 0)
        scores.append(points)
    if scores[0] == scores[1]:  # overtime decides it
        scores[0] += 2
        w.add(5, 30, home[0], g.pick(starters(home[1])), "shot", outcome="made", x=94, y=50, value=2,
              attributes={"shot_zone": "rim"})
    return scores[0], scores[1]


# ---------------------------------------------------------------------------
# Ice hockey: shifts by line and pair, shots with danger, goals
# ---------------------------------------------------------------------------


def ice_hockey(w: EventWriter, sport: dict, home: tuple[Any, list], away: tuple[Any, list]) -> tuple[int, int]:
    g = w.g
    goals = []
    for team_id, squad in (home, away):
        centres, wingers, defence = lineup(squad, "centre"), lineup(squad, "winger"), lineup(squad, "defenceman")
        lines = [[centres[i], wingers[2 * i], wingers[2 * i + 1]] for i in range(4)]
        pairs = [defence[2 * j: 2 * j + 2] for j in range(3)]
        goalie = lineup(squad, "goaltender")[0]
        on_ice: list[tuple[int, float, float, list[Any]]] = []
        for period in (1, 2, 3):
            w.shift(goalie, team_id, period, 0, 1200)
            t, i = 0.0, 0
            while t < 1200:
                length = min(g.between(38, 55), 1200 - t)
                line = lines[g.rng.choices(range(4), [0.34, 0.29, 0.22, 0.15])[0] if i else 0]
                pair = pairs[g.rng.choices(range(3), [0.4, 0.35, 0.25])[0]]
                for p in line + pair:
                    w.shift(p, team_id, period, t, t + length)
                on_ice.append((period, t, t + length, line + pair))
                t, i = t + length, i + 1
        scored = 0
        for _ in range(g.rng.randint(24, 38)):
            period, start, end, skaters = g.pick(on_ice)
            shooter = g.rng.choices(skaters, [1.3 if p.role != "defenceman" else 0.6 for p in skaters])[0]
            x, y = g.between(55, 97), g.between(10, 90)
            distance = math.hypot(100 - x, (50 - y) * 0.85)
            xg = min(0.45, 0.35 * math.exp(-distance / 14))
            danger = "high" if distance < 15 else "medium" if distance < 30 else "low"
            goal = g.chance(xg * 1.1)
            scored += goal
            assister = g.pick([p for p in skaters if p is not shooter]) if goal else None
            w.add(period, g.between(start, end), team_id, shooter, "shot", outcome="goal" if goal else "saved",
                  related=assister, x=x, y=y, value=xg, attributes={"shot_danger": danger, "strength": "5v5"})
        goals.append(scored)
    if goals[0] == goals[1]:
        goals[0] += 1
        w.add(4, 120, home[0], lineup(home[1], "centre")[0], "shot", outcome="goal", x=92, y=50, value=0.3,
              attributes={"shot_danger": "high", "strength": "3v3"})
    return goals[0], goals[1]


# ---------------------------------------------------------------------------
# Cricket (T20): ball-by-ball deliveries
# ---------------------------------------------------------------------------

LINE_X = {"wide outside off": 10, "outside off": 30, "stumps": 50, "leg stump": 65, "down leg": 85}
LENGTH_Y = {"yorker": 5, "full": 25, "good length": 45, "back of a length": 65, "short": 88}
BATTING_ORDER = ("opening_batter", "top_order_batter", "wicketkeeper_batter", "middle_order_batter", "finisher",
                 "all_rounder", "fast_bowler", "spin_bowler")


def cricket(w: EventWriter, sport: dict, home: tuple[Any, list], away: tuple[Any, list]) -> tuple[int, int]:
    g = w.g
    tags = {t["key"]: t["values"] for t in sport["videoTags"]}
    totals = []
    for innings, (batting, bowling) in enumerate(((home, away), (away, home)), start=1):
        xi = starters(batting[1])
        order = sorted(xi, key=lambda p: (BATTING_ORDER.index(p.role), p.depth))
        bowlers = [p for p in starters(bowling[1]) if p.role in ("fast_bowler", "spin_bowler", "all_rounder")]
        while len(bowlers) < 5:
            bowlers.append(bowlers[len(bowlers) % len(bowlers)])
        striker, non_striker, next_in = order[0], order[1], 2
        runs = wickets = 0
        target = totals[0] + 1 if innings == 2 else None
        for over in range(20):
            bowler = bowlers[over % 5]
            phase = "powerplay" if over < 6 else "death overs" if over >= 16 else "middle overs"
            ball = 0
            while ball < 6:
                length = g.rng.choices(list(LENGTH_Y), [8, 22, 40, 20, 10])[0]
                line = g.rng.choices(list(LINE_X), [10, 35, 35, 15, 5])[0]
                delivery = g.pick(tags["delivery_type"][:6] if bowler.role != "spin_bowler" else tags["delivery_type"][6:])
                attrs = {"over": over + 1, "ball": ball + 1, "length": length, "line": line, "delivery_type": delivery, "phase": phase}
                if g.chance(0.035):
                    attrs.update(extras=1, extra_type="wide", runs_bat=0)
                    runs += 1
                    w.add(innings, None, bowling[0], bowler, "delivery", related=striker, outcome="extra",
                          x=LINE_X[line] + g.rng.gauss(0, 3), y=LENGTH_Y[length] + g.rng.gauss(0, 3), value=1, attributes=attrs)
                    continue
                ball += 1
                aggression = 1.35 if phase == "death overs" else 1.15 if phase == "powerplay" else 1.0
                if g.chance(0.045 * aggression):
                    wickets += 1
                    attrs.update(runs_bat=0, dismissal=g.pick(("caught", "bowled", "lbw", "run out", "stumped" if bowler.role == "spin_bowler" else "caught")))
                    w.add(innings, None, bowling[0], bowler, "delivery", related=striker, outcome="wicket",
                          x=LINE_X[line] + g.rng.gauss(0, 3), y=LENGTH_Y[length] + g.rng.gauss(0, 3), value=0, attributes=attrs)
                    if wickets == 10 or next_in >= len(order):
                        break
                    striker, next_in = order[next_in], next_in + 1
                    continue
                scored = g.rng.choices((0, 1, 2, 3, 4, 6), [36, 33, 8, 1, 14 * aggression, 6 * aggression])[0]
                attrs.update(runs_bat=scored, shot=g.pick(tags["shot"]))
                end = None
                if scored:
                    angle = g.between(0, 2 * math.pi)
                    reach = {1: 18, 2: 30, 3: 38, 4: 48, 6: 50}[scored]
                    end = (50 + reach * math.cos(angle), 50 + reach * math.sin(angle))
                runs += scored
                w.add(innings, None, bowling[0], bowler, "delivery", related=striker, outcome="runs",
                      x=LINE_X[line] + g.rng.gauss(0, 3), y=LENGTH_Y[length] + g.rng.gauss(0, 3),
                      end_x=end[0] if end else None, end_y=end[1] if end else None, value=scored, attributes=attrs)
                if scored % 2:
                    striker, non_striker = non_striker, striker
                if target and runs >= target:
                    break
            striker, non_striker = non_striker, striker
            if wickets == 10 or (target and runs >= target):
                break
        totals.append(runs)
    if totals[0] == totals[1]:
        totals[1] += 1  # super over, recorded as a one-run margin
    return totals[0], totals[1]


# ---------------------------------------------------------------------------
# Baseball: pitch-by-pitch
# ---------------------------------------------------------------------------

PITCH_PROFILE = {  # pitch type: (velocity mph, spin rpm)
    "four-seam fastball": (95, 2350), "sinker": (93.5, 2150), "cutter": (90, 2400), "slider": (86, 2500),
    "sweeper": (82, 2650), "curveball": (79, 2700), "changeup": (86, 1750), "splitter": (87, 1400),
}
PITCH_LOCATIONS = {"up and in": (35, 75), "up and away": (65, 75), "down and in": (35, 25), "down and away": (65, 25),
                   "middle": (50, 50), "chase": (85, 10)}


def count_state(balls: int, strikes: int) -> str:
    """Ball-strike count as the pitcher sees it, in the sport's 'count' tag vocabulary."""
    if balls == strikes == 0:
        return "0-0"
    if balls == 3 and strikes == 2:
        return "full count"
    if strikes == 2:
        return "two strikes"
    return "ahead" if strikes > balls else "behind" if balls > strikes else "even"


def baseball(w: EventWriter, sport: dict, home: tuple[Any, list], away: tuple[Any, list]) -> tuple[int, int]:
    g = w.g
    runs_by_team = [0, 0]
    staffs = {}
    for side, (team_id, squad) in enumerate((home, away)):
        starter = g.pick(lineup(squad, "starting_pitcher"))
        relievers = lineup(squad, "relief_pitcher")[:4]
        repertoire = g.rng.sample(list(PITCH_PROFILE)[1:], 3)
        staffs[side] = (starter, relievers, repertoire)
    batting_orders = {side: [p for p in starters(squad) if "pitcher" not in p.role][:9] for side, (_, squad) in enumerate((home, away))}
    next_batter = [0, 0]
    for inning in range(1, 10):
        for half, (bat_side, field_side) in enumerate(((1, 0), (0, 1))):
            if inning == 9 and bat_side == 0 and runs_by_team[0] > runs_by_team[1]:
                continue  # home side leads: bottom of the ninth not needed
            team_id = (home, away)[field_side][0]
            starter, relievers, repertoire = staffs[field_side]
            pitcher = starter if inning <= 6 else relievers[(inning - 7) % len(relievers)]
            outs, bases = 0, [False, False, False]
            while outs < 3:
                order = batting_orders[bat_side]
                batter = order[next_batter[bat_side] % len(order)]
                next_batter[bat_side] += 1
                balls = strikes = 0
                while True:
                    pitch_type = g.rng.choices(["four-seam fastball", *repertoire], [50, 20, 18, 12])[0]
                    velo, spin = PITCH_PROFILE[pitch_type]
                    location = g.rng.choices(list(PITCH_LOCATIONS), [14, 14, 18, 20, 16, 18])[0]
                    lx, ly = PITCH_LOCATIONS[location]
                    roll = g.rng.random()
                    if location == "chase":
                        outcome = "ball" if roll < 0.62 else "swinging_strike" if roll < 0.85 else "foul"
                    else:
                        outcome = ("called_strike" if roll < 0.17 else "swinging_strike" if roll < 0.28 else
                                   "foul" if roll < 0.46 else "ball" if roll < 0.66 else "in_play")
                    attrs = {"pitch_type": pitch_type, "velocity_mph": round(g.rng.gauss(velo, 1.1), 1),
                             "spin_rpm": round(g.rng.gauss(spin, 90)), "location": location,
                             "balls_strikes": f"{balls}-{strikes}", "count": count_state(balls, strikes),
                             "inning": inning, "half": "top" if half == 0 else "bottom"}
                    result = None
                    if outcome == "ball":
                        balls += 1
                        result = "walk" if balls == 4 else None
                    elif outcome in ("called_strike", "swinging_strike") or (outcome == "foul" and strikes < 2):
                        strikes += 1
                        result = "strikeout" if strikes == 3 else None
                    elif outcome == "in_play":
                        result = g.rng.choices(("out", "single", "double", "triple", "home_run"), [68, 20, 6, 0.6, 3.4])[0]
                        attrs["batted_ball"] = g.pick(("ground ball", "line drive", "fly ball", "pop-up")) if result == "out" else \
                            ("barrel" if result == "home_run" else g.pick(("line drive", "ground ball", "fly ball")))
                    scored = 0
                    if result in ("out", "strikeout"):
                        outs += 1
                    elif result == "walk":
                        if bases[0] and bases[1] and bases[2]:
                            scored = 1
                        bases = [True, bases[0] or bases[1], bases[2] or (bases[0] and bases[1])]
                    elif result:
                        advance = {"single": 1, "double": 2, "triple": 3, "home_run": 4}[result]
                        runners = [i for i, b in enumerate(bases) if b]
                        scored = sum(1 for i in runners if i + advance >= 3) + (1 if advance == 4 else 0)
                        new = [False, False, False]
                        for i in runners:
                            if i + advance < 3:
                                new[i + advance] = True
                        if advance < 4:
                            new[advance - 1] = True
                        bases = new
                    runs_by_team[bat_side] += scored
                    if result:
                        attrs["result"] = result
                    w.add(inning, None, team_id, pitcher, "pitch", related=batter, outcome=outcome,
                          x=lx + g.rng.gauss(0, 6), y=ly + g.rng.gauss(0, 6), value=scored or None, attributes=attrs)
                    if result or outs >= 3:
                        break
                if inning == 9 and bat_side == 0 and runs_by_team[0] > runs_by_team[1]:
                    break  # walk-off
    if runs_by_team[0] == runs_by_team[1]:
        runs_by_team[0] += 1  # extra innings, recorded as a one-run margin
    return runs_by_team[0], runs_by_team[1]


# ---------------------------------------------------------------------------
# American football: drive and play simulation
# ---------------------------------------------------------------------------


def american_football(w: EventWriter, sport: dict, home: tuple[Any, list], away: tuple[Any, list]) -> tuple[int, int]:
    g = w.g
    tags = {t["key"]: t["values"] for t in sport["videoTags"]}
    points = [0, 0]
    for drive in range(22):
        side = drive % 2
        team_id, squad = (home, away)[side]
        qb = lineup(squad, "quarterback")[0]
        backs = lineup(squad, "running_back")[:2]
        targets = lineup(squad, "wide_receiver")[:3] + lineup(squad, "tight_end")[:1] + backs[:1]
        kicker = lineup(squad, "kicker")[0]
        period = min(drive // 6 + 1, 4)
        x, down, to_go = 25.0, 1, 10.0
        for _ in range(16):
            formation = g.pick(tags["offensive_formation"])
            coverage = g.pick(tags["coverage"])
            down_label = ("1st & 10" if down == 1 else "2nd & long" if down == 2 and to_go > 6 else "2nd & short" if down == 2
                          else "3rd & long" if down == 3 and to_go > 5 else "3rd & short" if down == 3 else "4th down")
            if x >= 80:
                down_label = "red zone"
            attrs = {"offensive_formation": formation, "personnel": g.pick(tags["personnel"]), "coverage": coverage,
                     "down_distance": down_label, "down": down, "to_go": round(to_go)}
            if g.chance(0.56):
                target = g.pick(targets)
                complete = g.chance(0.64)
                yards = max(-2.0, g.rng.gauss(11, 8)) if complete else 0.0
                turnover = not complete and g.chance(0.04)
                attrs["route"] = g.pick(tags["route"])
                kind, carrier, outcome = "pass", qb, "interception" if turnover else "complete" if complete else "incomplete"
                related = target
            else:
                yards = g.rng.gauss(4.3, 4.5)
                turnover = g.chance(0.012)
                kind, carrier, outcome, related = "rush", g.pick(backs), "fumble" if turnover else "gain", None
            yards = min(yards, 100 - x)
            needed = to_go * (0.4 if down == 1 else 0.6 if down == 2 else 1.0)
            attrs["success"] = bool(yards >= needed and not turnover)
            touchdown = x + yards >= 100 and not turnover
            if touchdown:
                outcome = "touchdown"
            w.add(period, None, team_id, carrier, kind, related=related, outcome=outcome, x=x, y=g.between(20, 80),
                  end_x=min(x + yards, 100), value=round(yards, 1), attributes=attrs)
            if turnover:
                break
            if touchdown:
                points[side] += 7
                break
            x += yards
            if yards >= to_go:
                down, to_go = 1, min(10.0, 100 - x)
            else:
                down, to_go = down + 1, to_go - yards
            if down == 4:
                if x >= 62:
                    made = g.chance(0.86 if x >= 75 else 0.7)
                    points[side] += 3 if made else 0
                    w.add(period, None, team_id, kicker, "field_goal", outcome="made" if made else "missed", x=x, y=50,
                          value=round(117 - x, 1))
                else:
                    punter = lineup(squad, "punter")[0]
                    w.add(period, None, team_id, punter, "punt", outcome="returned", x=x, y=50, value=round(g.between(38, 50), 1))
                break
    if points[0] == points[1]:
        points[0] += 3  # overtime field goal
    return points[0], points[1]


SIMULATORS: dict[str, Callable[..., tuple[int, int]]] = {
    "soccer": soccer, "basketball": basketball, "ice_hockey": ice_hockey,
    "cricket": cricket, "baseball": baseball, "american_football": american_football,
}


def simulate_match(g: Any, rows: Any, sport: dict, match: dict[str, Any], squads: dict[Any, list]) -> None:
    writer = EventWriter(g, rows, match)
    home = (match["home_team_id"], squads[match["home_team_id"]])
    away = (match["away_team_id"], squads[match["away_team_id"]])
    match["home_score"], match["away_score"] = SIMULATORS[sport["id"]](writer, sport, home, away)
