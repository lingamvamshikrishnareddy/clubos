"""Deterministic fictional demo data for all six sports and every stage of the product.

Per sport: a ten-team league with two completed seasons (fixtures, results, season stats
and market transactions) and one demo club with staff, contracts, scouting, video,
training load, availability, development, academy, facilities, finance and commercial
data. Everything is recorded under the 'mock' data source.

Model outputs (valuations, forecasts, recommendations, workload indicators) are not
invented here: run `clubos-ml run` afterwards to compute them from this data.
"""

from __future__ import annotations

import json
import math
import os
import random
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .mock_config import FIRST_NAMES, LAST_NAMES, LEAGUES, NATIONALITIES, LeagueConfig
from .mock_events import simulate_match

SOURCE_ID = "mock"


def sports_dir() -> Path:
    """packages/sports: $CLUBOS_SPORTS_DIR, else found by searching up from this file or the
    working directory, so it works from a checkout or an installed package."""
    if override := os.environ.get("CLUBOS_SPORTS_DIR"):
        return Path(override)
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        for parent in start.parents:
            if (parent / "packages" / "sports").is_dir():
                return parent / "packages" / "sports"
    raise FileNotFoundError("packages/sports not found; set CLUBOS_SPORTS_DIR")


def load_sport(slug: str) -> dict[str, Any]:
    return json.loads((sports_dir() / slug / "sport.json").read_text())


# ---------------------------------------------------------------------------
# Row buffer: rows are collected per table and written in foreign-key order.
# ---------------------------------------------------------------------------

TABLE_ORDER = (
    "organisations", "app_users", "memberships", "staff_profiles", "competitions", "seasons", "teams",
    "source_entity_ids", "matches", "players", "player_identities", "player_season_stats",
    "player_season_metric_values", "market_transactions", "squad_members", "contracts", "scouting_reports",
    "shortlists", "shortlist_entries", "club_style_profiles", "videos", "video_events", "clips", "clip_events",
    "playlists", "playlist_clips", "scouting_report_clips", "tactical_reports", "budget_scenarios",
    "budget_scenario_moves", "training_sessions", "session_loads", "wellness_checkins", "availability_status",
    "medical_records", "development_goals", "assessments", "facilities", "facility_bookings", "calendar_events",
    "attendance", "tasks", "announcements", "guardians", "academy_registrations", "academy_fees", "payments",
    "budgets", "sponsors", "sponsorship_deals", "ad_inventory", "ad_bookings", "stadium_events",
    "financial_transactions", "match_events", "player_shifts", "academy_renewals", "payroll_runs", "payslips",
    "message_threads", "message_participants", "messages", "decisions", "decision_outcomes",
)


@dataclass
class Rows:
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

    def add(self, table: str, **row: Any) -> dict[str, Any]:
        assert table in TABLE_ORDER, table
        self.tables.setdefault(table, []).append(row)
        return row

    def write(self, conn: psycopg.Connection) -> dict[str, int]:
        counts = {}
        with conn.cursor() as cur:
            for table in TABLE_ORDER:
                rows = self.tables.get(table, [])
                if not rows:
                    continue
                columns = list(rows[0])
                sql = f"insert into {table} ({', '.join(columns)}) values ({', '.join(['%s'] * len(columns))})"
                cur.executemany(sql, [[_adapt(c, row[c]) for c in columns] for row in rows])
                counts[table] = len(rows)
        return counts


JSONB_COLUMNS = {"attributes", "tags", "findings", "clauses", "metric_weights", "external_load", "results", "deliverables",
                 "bonus_detail", "expected_outcome", "actual"}


def _adapt(column: str, value: Any) -> Any:
    return Jsonb(value) if column in JSONB_COLUMNS else value


# ---------------------------------------------------------------------------
# Generation helpers
# ---------------------------------------------------------------------------


class Gen:
    def __init__(self, seed: int, as_of: date):
        self.rng = random.Random(seed)
        self.as_of = as_of

    def id(self) -> uuid.UUID:
        return uuid.UUID(int=self.rng.getrandbits(128), version=4)

    def name(self) -> str:
        return f"{self.rng.choice(FIRST_NAMES)} {self.rng.choice(LAST_NAMES)}"

    def between(self, low: float, high: float) -> float:
        return self.rng.uniform(low, high)

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    def pick(self, seq: Iterable[Any]) -> Any:
        return self.rng.choice(list(seq))

    def day_in(self, start: date, end: date) -> date:
        return start + timedelta(days=self.rng.randint(0, max((end - start).days, 0)))


def d(iso: str) -> date:
    return date.fromisoformat(iso)


def at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc)


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def money(x: float) -> float:
    return round(x, -2) if x >= 10_000 else round(x, 2)


@dataclass
class MockPlayer:
    id: uuid.UUID
    name: str
    role: str
    birth_date: date
    quality: float  # latent ability, roughly N(0, 1)
    team_index: int
    depth: int  # 0 = first choice in role
    starter: bool

    def age_on(self, day: date) -> int:
        return day.year - self.birth_date.year - ((day.month, day.day) < (self.birth_date.month, self.birth_date.day))


def market_value(cfg: LeagueConfig, player: MockPlayer, on: date, rng: random.Random) -> tuple[float, float | None]:
    """(annual salary, transfer fee or None) the fictional market would pay."""
    age = player.age_on(on)
    signal = 1.25 * player.quality - ((age - 27) / 6) ** 2 + (0.5 if player.starter else -0.4)
    share = sigmoid(signal + rng.gauss(0, 0.35))
    low, high = cfg.salary_range
    salary = low * (high / low) ** (share ** 1.6)
    fee = None
    if cfg.fee_range:
        f_low, f_high = cfg.fee_range
        fee = f_low * (f_high / f_low) ** (sigmoid(signal + 0.4 * (27 - age) / 5 + rng.gauss(0, 0.35)) ** 1.6)
    return money(salary), money(fee) if fee is not None else None


# ---------------------------------------------------------------------------
# League: competition, seasons, teams, fixtures, players, season stats, market
# ---------------------------------------------------------------------------


@dataclass
class League:
    cfg: LeagueConfig
    sport: dict[str, Any]
    org_id: uuid.UUID
    team_ids: list[uuid.UUID]
    season_ids: list[uuid.UUID]
    players: list[MockPlayer]
    matches: list[dict[str, Any]]  # rows of the latest season
    academy_team_id: uuid.UUID


def exposure_for_role(sport: dict, role: str) -> dict:
    return (sport.get("roleExposure") or {}).get(role, sport["exposure"])


def build_league(g: Gen, rows: Rows, sport_id: str) -> League:
    cfg = LEAGUES[sport_id]
    sport = load_sport(cfg.slug)
    org_id = g.id()
    rows.add("organisations", id=org_id, name=cfg.club, primary_sport=sport_id)

    competition_id = g.id()
    rows.add("competitions", id=competition_id, sport_id=sport_id, name=cfg.league, country=cfg.country,
             gender="men", tier=1, is_youth=False, attributes=dict(cfg.competition_attributes))
    rows.add("source_entity_ids", source_id=SOURCE_ID, entity_type="competition",
             external_id=f"{sport_id}:league", entity_id=competition_id)

    season_ids = []
    for season in cfg.seasons:
        season_id = g.id()
        season_ids.append(season_id)
        rows.add("seasons", id=season_id, competition_id=competition_id, label=season.label,
                 starts_on=d(season.starts_on), ends_on=d(season.ends_on))

    team_ids = []
    for i, team in enumerate(cfg.teams):
        team_id = g.id()
        team_ids.append(team_id)
        rows.add("teams", id=team_id, sport_id=sport_id, name=team, country=cfg.country,
                 organisation_id=org_id if i == 0 else None)
    academy_team_id = g.id()
    rows.add("teams", id=academy_team_id, sport_id=sport_id, name=f"{cfg.teams[0]} Academy U18",
             country=cfg.country, organisation_id=org_id)

    # Players: a full roster per team.
    players: list[MockPlayer] = []
    reference_day = d(cfg.seasons[0].starts_on)
    for team_index in range(len(cfg.teams)):
        for role, (size, starters) in cfg.roster.items():
            qualities = sorted((g.rng.gauss(0, 1) for _ in range(size)), reverse=True)
            for depth, quality in enumerate(qualities):
                age = g.rng.randint(19, 34) if depth < starters else g.rng.randint(18, 31)
                birth = reference_day - timedelta(days=age * 365 + g.rng.randint(0, 364))
                players.append(MockPlayer(g.id(), g.name(), role, birth, quality + (0.3 if team_index == 0 else 0),
                                          team_index, depth, depth < starters))

    for p in players:
        attributes = sport_attributes(g, sport_id, p.role)
        rows.add("players", id=p.id, sport_id=sport_id, full_name=p.name, known_as=None, birth_date=p.birth_date,
                 nationality=g.pick(cfg_nationalities(cfg)), primary_role=p.role, attributes=attributes)
        rows.add("player_identities", source_id=SOURCE_ID, external_id=f"{sport_id}:{p.id}", player_id=p.id,
                 match_method="exact", confidence=1)

    # Fixtures, results and season stats for both seasons.
    latest_matches: list[dict[str, Any]] = []
    for s_index, (season, season_id) in enumerate(zip(cfg.seasons, season_ids)):
        if s_index == 1:
            develop(g, players, d(season.starts_on))
        matches = fixtures(g, cfg, season, season_id, team_ids)
        # Keep the stored rows, so scores set later from simulated play-by-play are written.
        matches = [rows.add("matches", **match) for match in matches]
        for match in matches:
            rows.add("source_entity_ids", source_id=SOURCE_ID, entity_type="match",
                     external_id=f"{sport_id}:{match['id']}", entity_id=match["id"])
        if s_index == 1:
            latest_matches = matches
        for p in players:
            season_stats(g, rows, cfg, sport, p, season_id, team_ids[p.team_index], season.label)

    # Market transactions: about 40% of players have a recent recorded move.
    for p in players:
        if not g.chance(0.4):
            continue
        on = g.day_in(g.as_of - timedelta(days=3 * 365), g.as_of - timedelta(days=30))
        salary, fee = market_value(cfg, p, on, g.rng)
        kind = g.pick(cfg.market_kinds)
        from_team = None if kind in ("draft", "auction", "free_agent_signing") else team_ids[(p.team_index + 3) % len(team_ids)]
        rows.add("market_transactions", id=g.id(), player_id=p.id, kind=kind, occurred_on=on,
                 from_team_id=from_team, to_team_id=team_ids[p.team_index], currency=cfg.currency,
                 fee=fee if kind in ("transfer", "trade") and not g.chance(0.15) else None,  # some undisclosed
                 annual_salary=salary, contract_years=g.rng.randint(1, 5),
                 source_id=SOURCE_ID, source_record_id=f"{sport_id}:market:{p.id}:{on}")

    return League(cfg, sport, org_id, team_ids, season_ids, players, latest_matches, academy_team_id)


def cfg_nationalities(cfg: LeagueConfig) -> tuple[str, ...]:
    pools = {
        "INR": ("India", "India", "India", "India", "Australia", "England", "South Africa", "New Zealand", "Sri Lanka", "Jamaica"),
        "USD": ("United States", "United States", "United States", "Canada", "Mexico", "Japan", "South Korea", "Nigeria", "Australia"),
        "CAD": ("Canada", "Canada", "Canada", "United States", "Sweden", "Norway", "Germany", "Netherlands"),
    }
    return pools.get(cfg.currency, NATIONALITIES)


def sport_attributes(g: Gen, sport_id: str, role: str) -> dict[str, Any]:
    height = round(g.rng.gauss(185, 7))
    if sport_id == "soccer":
        return {"preferred_foot": g.pick(("right", "right", "right", "left", "both")), "height_cm": height}
    if sport_id == "american_football":
        return {"height_cm": height, "weight_kg": round(g.rng.gauss(140 if role in ("offensive_line", "defensive_line") else 100, 8))}
    if sport_id == "baseball":
        return {"bats": g.pick(("R", "R", "L", "S")), "throws": g.pick(("R", "R", "R", "L")), "height_cm": height}
    if sport_id == "basketball":
        base = {"point_guard": 188, "shooting_guard": 196, "small_forward": 201, "power_forward": 206, "centre": 211}[role]
        return {"height_cm": round(g.rng.gauss(base, 3)), "wingspan_cm": round(g.rng.gauss(base + 6, 4))}
    if sport_id == "ice_hockey":
        return {"shoots": g.pick(("L", "L", "R")), "height_cm": height}
    if sport_id == "cricket":
        attrs: dict[str, Any] = {"batting_hand": g.pick(("right", "right", "right", "left"))}
        if role in ("fast_bowler", "all_rounder"):
            attrs["bowling_style"] = g.pick(("right-arm fast", "right-arm fast-medium", "left-arm fast-medium"))
        if role == "spin_bowler":
            attrs["bowling_style"] = g.pick(("right-arm off-break", "right-arm leg-break", "left-arm orthodox"))
        return attrs
    return {}


def develop(g: Gen, players: list[MockPlayer], on: date) -> None:
    """Between seasons: young players improve, older players decline."""
    for p in players:
        age = p.age_on(on)
        delta = g.rng.gauss(0.25, 0.15) if age < 23 else g.rng.gauss(0.03, 0.1) if age <= 29 else g.rng.gauss(-0.15, 0.1)
        p.quality += delta


def fixtures(g: Gen, cfg: LeagueConfig, season, season_id: uuid.UUID, team_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    n = len(team_ids)
    rounds_needed = cfg.games_per_team
    # Circle-method round robin, repeated with home and away swapped.
    order = list(range(n))
    rounds: list[list[tuple[int, int]]] = []
    while len(rounds) < rounds_needed:
        for r in range(n - 1):
            pairs = [(order[i], order[n - 1 - i]) for i in range(n // 2)]
            # Alternate home and away round by round (the circle method's fixed team would
            # otherwise always be at home), and reverse every fixture in the second cycle.
            if (r % 2 == 1) != ((len(rounds) // (n - 1)) % 2 == 1):
                pairs = [(b, a) for a, b in pairs]
            rounds.append(pairs)
            order = [order[0]] + [order[-1]] + order[1:-1]
            if len(rounds) == rounds_needed:
                break
    start, end = d(season.starts_on), d(season.ends_on)
    span = (end - start).days
    matches = []
    for r, pairs in enumerate(rounds):
        day = start + timedelta(days=round(span * r / max(len(rounds) - 1, 1)))
        for home, away in pairs:
            home_score, away_score = score(g, cfg), score(g, cfg)
            if cfg.slug in ("basketball", "american-football", "cricket") and home_score == away_score:
                home_score += 1  # no draws in these leagues
            matches.append({
                "id": g.id(), "season_id": season_id, "home_team_id": team_ids[home], "away_team_id": team_ids[away],
                "kickoff_at": at(day, 19), "home_score": home_score, "away_score": away_score,
            })
    return matches


def score(g: Gen, cfg: LeagueConfig) -> int:
    kind, mean, sd = cfg.score
    if kind == "poisson":
        # Knuth's algorithm; means here are small.
        threshold, k, p = math.exp(-mean), 0, 1.0
        while True:
            p *= g.rng.random()
            if p <= threshold:
                return k
            k += 1
    return max(0, round(g.rng.gauss(mean, sd)))


def season_stats(g: Gen, rows: Rows, cfg: LeagueConfig, sport: dict, p: MockPlayer, season_id: uuid.UUID,
                 team_id: uuid.UUID, season_label: str) -> None:
    exposure_unit = exposure_for_role(sport, p.role)
    starter, backup = cfg.exposure_per_game.get(p.role, cfg.exposure_per_game["default"])
    per_game = starter if p.starter else backup
    if per_game == 0:
        return
    played = round(cfg.games_per_team * (g.between(0.75, 1.0) if p.starter else g.between(0.3, 0.85)))
    if played == 0:
        return
    exposure = round(played * per_game * g.between(0.85, 1.1), 1)
    stats_id = g.id()
    rows.add("player_season_stats", id=stats_id, player_id=p.id, season_id=season_id, team_id=team_id,
             role_key=p.role, exposure=exposure, exposure_unit=exposure_unit["key"], appearances=played,
             source_id=SOURCE_ID, source_record_id=f"{p.id}:{season_label}", ingestion_run_id=None,
             ingested_at=datetime.now(timezone.utc))

    metrics = {m["key"]: m for m in sport["metrics"]}
    # Smaller samples are noisier, as in real data.
    noise = 0.07 + 0.12 * math.sqrt(exposure_unit["minimumForComparison"] / max(exposure, 1))
    for key in sport["comparisonMetrics"][p.role]:
        m = metrics[key]
        low, high = m["typical"]
        position = sigmoid(0.85 * p.quality + g.rng.gauss(0, 3 * noise))
        if not m["higherIsBetter"]:
            position = 1 - position
        value = low + (high - low) * position
        if m["normalisation"] == "per_exposure":
            value = value * exposure / exposure_unit["per"]
            value = round(value) if m["unit"] in ("count", "points", "runs", "yards") else round(value, 3)
        else:
            value = round(value, 3)
        rows.add("player_season_metric_values", season_stats_id=stats_id, metric_key=key, value=value)


# ---------------------------------------------------------------------------
# Club operations (one demo club per sport)
# ---------------------------------------------------------------------------

STAFF = (
    ("admin", "Club administrator", "operations"),
    ("sporting_director", "Sporting director", "recruitment"),
    ("head_coach", "Head coach", "coaching"),
    ("analyst", "Lead performance analyst", "analysis"),
    ("scout", "Chief scout", "recruitment"),
    ("scout", "Scout", "recruitment"),
    ("performance", "Head of performance", "performance"),
    ("medical", "Club doctor", "medical"),
    ("finance", "Finance director", "finance"),
    ("executive", "Chief executive", "executive"),
    ("head_coach", "Academy head coach", "academy"),
)


def build_club(g: Gen, rows: Rows, lg: League) -> None:
    cfg, sport, org = lg.cfg, lg.sport, lg.org_id
    cur = cfg.currency
    sport_id = sport["id"]
    slug = cfg.slug.replace("-", "")
    as_of = g.as_of
    fy = as_of.year
    scale = {"INR": 85.0, "CAD": 1.35}.get(cur, 1.0)  # rough unit scale for operating costs

    # Staff -----------------------------------------------------------------
    staff: dict[str, list[uuid.UUID]] = {}
    staff_salaries = 0.0
    for role, title, department in STAFF:
        user_id = g.id()
        first, last = g.pick(FIRST_NAMES), g.pick(LAST_NAMES)
        rows.add("app_users", id=user_id, email=f"{first}.{last}.{len(rows.tables.get('app_users', []))}@{slug}.example".lower(),
                 display_name=f"{first} {last}")
        rows.add("memberships", organisation_id=org, user_id=user_id, role=role)
        salary = money(g.between(60_000, 400_000) * scale)
        staff_salaries += salary
        rows.add("staff_profiles", user_id=user_id, organisation_id=org, job_title=title, department=department,
                 annual_salary=salary, currency=cur, started_on=as_of - timedelta(days=g.rng.randint(100, 3000)))
        staff.setdefault(role, []).append(user_id)
    scout_ids = staff["scout"]
    analyst = staff["analyst"][0]
    medical = staff["medical"][0]
    performance = staff["performance"][0]
    director = staff["sporting_director"][0]
    coach = staff["head_coach"][0]

    # Squad and contracts ---------------------------------------------------------
    own = [p for p in lg.players if p.team_index == 0]
    others = [p for p in lg.players if p.team_index != 0]
    wage_bill = 0.0
    contract_by_player: dict[uuid.UUID, dict[str, Any]] = {}
    for i, p in enumerate(own):
        status = "first_team" if p.starter or p.depth == 1 else ("loaned_out" if i % 9 == 0 else "reserve")
        ends = date(as_of.year + g.rng.randint(0, 4), 6, 30)
        rows.add("squad_members", organisation_id=org, player_id=p.id, role_key=p.role, status=status,
                 contract_expires_on=ends, joined_on=as_of - timedelta(days=g.rng.randint(60, 2000)), left_on=None)
        salary, fee = market_value(cfg, p, as_of, g.rng)
        starts = date(ends.year - g.rng.randint(2, 5), 7, 1)
        contract = rows.add("contracts", id=g.id(), organisation_id=org, player_id=p.id, starts_on=starts, ends_on=ends,
                            currency=cur, annual_salary=salary, signing_fee=money(salary * 0.1) if g.chance(0.3) else 0,
                            transfer_fee=fee if fee and g.chance(0.5) else 0,
                            clauses=[{"type": "appearance_bonus", "amount": money(salary * 0.002)}] if g.chance(0.4) else [],
                            status="active")
        contract_by_player[p.id] = contract
        wage_bill += salary

    # Academy players (not in the league) with guardians, registrations and fees.
    academy_players = []
    for _ in range(10):
        pid = g.id()
        role = g.pick(list(cfg.roster))
        birth = as_of - timedelta(days=g.rng.randint(15, 17) * 365 + g.rng.randint(0, 364))
        rows.add("players", id=pid, sport_id=sport_id, full_name=g.name(), known_as=None, birth_date=birth,
                 nationality=g.pick(cfg_nationalities(cfg)), primary_role=role, attributes=sport_attributes(g, sport_id, role))
        rows.add("squad_members", organisation_id=org, player_id=pid, role_key=role, status="academy",
                 contract_expires_on=None, joined_on=as_of - timedelta(days=g.rng.randint(30, 900)), left_on=None)
        academy_players.append((pid, role))
        guardian_id = g.id()
        rows.add("guardians", id=guardian_id, full_name=g.name(), email=f"guardian.{pid.hex[:8]}@example.com", phone=None)
        reg_id = g.id()
        rows.add("academy_registrations", id=reg_id, organisation_id=org, player_id=pid, guardian_id=guardian_id,
                 team_id=lg.academy_team_id, season_label=str(fy), status="active",
                 registered_on=date(fy, 1, 10), consent_media=g.chance(0.8), consent_medical=True)
        monthly_fee = money(150 * scale)
        offered_on = date(fy, 9, 1)
        if offered_on <= as_of:
            respond_by = offered_on + timedelta(days=30)
            if respond_by < as_of:
                status = g.rng.choices(("accepted", "declined", "lapsed"), [75, 15, 10])[0]
            else:
                status = g.rng.choices(("offered", "accepted"), [60, 40])[0]
            rows.add("academy_renewals", id=g.id(), registration_id=reg_id, next_season_label=str(fy + 1),
                     offered_on=offered_on, respond_by=respond_by, currency=cur, annual_fee=money(monthly_fee * 12),
                     status=status, responded_on=None if status in ("offered", "lapsed") else offered_on + timedelta(days=g.rng.randint(2, 25)),
                     notes=None)
        for month in range(1, as_of.month + 1):
            due = date(fy, month, 5)
            if due > as_of:
                break
            paid = g.chance(0.88) or month < as_of.month - 2
            fee_id = g.id()
            status = "paid" if paid else ("overdue" if (as_of - due).days > 14 else "due")
            rows.add("academy_fees", id=fee_id, registration_id=reg_id, description=f"Academy fee {due:%B %Y}",
                     currency=cur, amount=monthly_fee, due_on=due, status=status)
            if paid:
                paid_on = due + timedelta(days=g.rng.randint(0, 10))
                rows.add("payments", id=g.id(), academy_fee_id=fee_id, paid_on=paid_on, currency=cur, amount=monthly_fee,
                         method=g.pick(("card", "bank_transfer", "direct_debit", "upi" if cur == "INR" else "card")),
                         reference=f"ACD-{fee_id.hex[:8].upper()}")
                rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=paid_on, fiscal_year=paid_on.year,
                         category="academy_fees_income", currency=cur, amount=monthly_fee,
                         description="Academy fee payment", counterparty=None, player_id=pid, contract_id=None)

    # Recruitment: style profiles, scouting reports, shortlists ---------------------
    metric_defs = {m["key"]: m for m in sport["metrics"]}
    focus_roles = list(cfg.roster)[:: max(len(cfg.roster) // 3, 1)][:3]
    for role in focus_roles:
        keys = sport["comparisonMetrics"][role]
        weights = [0.3, 0.25, 0.2, 0.15, 0.1, 0.05, 0.05][: len(keys)]
        total = sum(weights)
        rows.add("club_style_profiles", id=g.id(), organisation_id=org, sport_id=sport_id, role_key=role,
                 name="First-team model", metric_weights={k: round(w / total, 3) for k, w in zip(keys, weights)})

    targets = sorted(others, key=lambda p: -p.quality)[:40]
    reports = []
    for p in g.rng.sample(targets, 14):
        rec = "sign" if p.quality > 1.4 else ("monitor" if p.quality > 0.6 else "reject")
        strengths = ", ".join(metric_defs[k]["label"].lower() for k in sport["comparisonMetrics"][p.role][:2])
        report = rows.add("scouting_reports", id=g.id(), organisation_id=org, player_id=p.id, author_id=g.pick(scout_ids),
                          match_id=g.pick(lg.matches)["id"], role_assessed=p.role,
                          rating=max(1, min(10, round(6 + 1.5 * p.quality + g.rng.gauss(0, 0.8)))),
                          summary=f"{p.name} looked comfortable as a {p.role.replace('_', ' ')} at this level.",
                          strengths=f"Consistently strong on {strengths}.",
                          weaknesses=g.pick(("Decision-making under pressure.", "Consistency across a full game.",
                                             "Physical output late in games.", "Weaker against top opposition.")),
                          recommendation=rec)
        reports.append((report, p))

    for role in focus_roles[:2]:
        sl_id = g.id()
        rows.add("shortlists", id=sl_id, organisation_id=org, name=f"{role.replace('_', ' ').title()} targets",
                 role_key=role, created_by=director)
        candidates = [p for p in targets if p.role == role][:5] or targets[:3]
        for p in candidates:
            rows.add("shortlist_entries", shortlist_id=sl_id, player_id=p.id,
                     stage=g.pick(("watch", "scout", "shortlist", "approach")), notes=None, added_by=g.pick(scout_ids))

    # Video and tactical evidence (Stage 2) -------------------------------------------
    own_team = lg.team_ids[0]
    club_matches = [m for m in lg.matches if own_team in (m["home_team_id"], m["away_team_id"])][-3:]
    by_team: dict[uuid.UUID, list[MockPlayer]] = {}
    for p in lg.players:
        by_team.setdefault(lg.team_ids[p.team_index], []).append(p)
    # Detailed play-by-play for these matches; scores are set from the simulated events.
    for match in club_matches:
        simulate_match(g, rows, sport, match, by_team)
    all_clips = []
    report_clips: list[tuple[uuid.UUID, uuid.UUID]] = []
    scouted = {p.id for _, p in reports}
    for match in club_matches:
        video_id = g.id()
        duration = 5400.0 if sport_id != "baseball" else 10800.0
        rows.add("videos", id=video_id, organisation_id=org, match_id=match["id"],
                 title=f"Match video {match['kickoff_at']:%d %b %Y}", storage_uri=f"mock://video/{video_id}.mp4",
                 duration_seconds=duration, angle=g.pick(("broadcast", "tactical")), kickoff_offset_seconds=120,
                 uploaded_by=analyst)
        events = []
        for _ in range(40):
            team = g.pick((match["home_team_id"], match["away_team_id"]))
            player = g.pick(by_team[team])
            start = round(g.between(120, duration - 30), 1)
            groups = g.rng.sample(sport["videoTags"], 2)
            ev = rows.add("video_events", id=g.id(), video_id=video_id, start_seconds=start,
                          end_seconds=round(start + g.between(3, 15), 1), event_type=g.pick(sport["eventTypes"])["key"],
                          player_id=player.id, team_id=team, x=round(g.between(0, 100), 2), y=round(g.between(0, 100), 2),
                          outcome=g.pick(("successful", "unsuccessful", None)),
                          tags={grp["key"]: g.pick(grp["values"]) for grp in groups},
                          tagged_by=analyst, tag_method="manual", created_at=datetime.now(timezone.utc))
            events.append((ev, player))
        for _ in range(3):
            chosen = g.rng.sample(events, 2)
            start = min(e["start_seconds"] for e, _ in chosen)
            clip_id = g.id()
            rows.add("clips", id=clip_id, video_id=video_id, title=f"{chosen[0][0]['event_type'].replace('_', ' ').title()} sequence",
                     start_seconds=max(start - 5, 0), end_seconds=max(e["end_seconds"] for e, _ in chosen) + 5,
                     notes=None, created_by=analyst)
            for e, player in chosen:
                rows.add("clip_events", clip_id=clip_id, event_id=e["id"])
                if player.id in scouted:
                    report_clips.append((player.id, clip_id))
            all_clips.append(clip_id)
    for name, purpose in (("Next opponent: set pieces", "opponent_analysis"), ("Individual feedback", "player_feedback")):
        pl_id = g.id()
        rows.add("playlists", id=pl_id, organisation_id=org, name=name, purpose=purpose, created_by=analyst)
        for pos, clip_id in enumerate(g.rng.sample(all_clips, min(4, len(all_clips)))):
            rows.add("playlist_clips", playlist_id=pl_id, clip_id=clip_id, position=pos)
    report_by_player = {p.id: r["id"] for r, p in reports}
    for player_id, clip_id in dict(report_clips).items():
        rows.add("scouting_report_clips", report_id=report_by_player[player_id], clip_id=clip_id)
    if club_matches:
        last = club_matches[-1]
        opponent = last["away_team_id"] if last["home_team_id"] == own_team else last["home_team_id"]
        tag_group = sport["videoTags"][0]
        rows.add("tactical_reports", id=g.id(), organisation_id=org, match_id=last["id"], opponent_team_id=opponent,
                 kind="post_match", title="Post-match review",
                 summary=f"Most chances conceded came from '{g.pick(tag_group['values'])}' situations.",
                 findings=[{"finding": f"Repeated issue in '{g.pick(tag_group['values'])}' ({tag_group['label'].lower()}).",
                            "evidence_clip_ids": [str(c) for c in all_clips[-2:]]}],
                 author_id=analyst, created_at=datetime.now(timezone.utc))

    # Budget scenario (Stage 3) -------------------------------------------------------------
    transfer_budget = money(wage_bill * 0.35)
    scenario_id = g.id()
    rows.add("budget_scenarios", id=scenario_id, organisation_id=org, name="Next window plan", fiscal_year=fy + 1,
             currency=cur, transfer_budget=transfer_budget, wage_budget=money(wage_bill * 1.08), created_by=director)
    signing = reports[0][1]
    salary, fee = market_value(cfg, signing, as_of, g.rng)
    rows.add("budget_scenario_moves", id=g.id(), scenario_id=scenario_id, player_id=signing.id, direction="in",
             transfer_fee=fee or 0, annual_salary=salary, contract_years=4)
    oldest = max(own, key=lambda p: p.age_on(as_of))
    rows.add("budget_scenario_moves", id=g.id(), scenario_id=scenario_id, player_id=oldest.id, direction="out",
             transfer_fee=0, annual_salary=contract_by_player[oldest.id]["annual_salary"], contract_years=1)

    # Facilities ----------------------------------------------------------------------
    facility_ids: dict[str, uuid.UUID] = {}
    for i, kind in enumerate(cfg.facility_kinds):
        fid = g.id()
        label = {"stadium": f"{cfg.teams[0]} Stadium", "meeting_room": "Analysis room", "medical_room": "Medical centre",
                 "gym": "Performance gym"}.get(kind, f"Training {kind} {i}")
        rows.add("facilities", id=fid, organisation_id=org, name=label, kind=kind,
                 capacity=cfg.stadium_capacity if kind == "stadium" else None)
        facility_ids.setdefault(kind, fid)
    training_facility = facility_ids[cfg.facility_kinds[1]]

    # Training load, wellness, availability (Stage 4) and calendar (Stage 5) ------------------
    senior = [p for p in own if p.starter or p.depth == 1]
    unavailable = {p.id: g.pick(("injury", "injury", "illness")) for p in g.rng.sample(senior, 3)}
    modified = {p.id for p in g.rng.sample([p for p in senior if p.id not in unavailable], 2)}
    spiking = {p.id for p in g.rng.sample([p for p in senior if p.id not in unavailable], 3)}
    for p_id, reason in unavailable.items():
        av_id = g.id()
        started = as_of - timedelta(days=g.rng.randint(3, 20))
        rows.add("availability_status", id=av_id, player_id=p_id, organisation_id=org, status="unavailable",
                 starts_on=started, expected_return_on=as_of + timedelta(days=g.rng.randint(5, 40)), ends_on=None,
                 reason_category=reason, set_by=medical, created_at=datetime.now(timezone.utc))
        rows.add("medical_records", id=g.id(), availability_id=av_id,
                 body_area=g.pick(("hamstring", "ankle", "knee", "shoulder", "lower back")) if reason == "injury" else None,
                 diagnosis="Fictional demo record", treatment_plan="Graduated return-to-play protocol",
                 recorded_by=medical, recorded_at=datetime.now(timezone.utc))
    for p_id in modified:
        rows.add("availability_status", id=g.id(), player_id=p_id, organisation_id=org, status="modified_training",
                 starts_on=as_of - timedelta(days=2), expected_return_on=as_of + timedelta(days=5), ends_on=None,
                 reason_category="load_management", set_by=performance, created_at=datetime.now(timezone.utc))

    start_day = as_of - timedelta(days=41)
    for offset in range(42):
        day = start_day + timedelta(days=offset)
        weekday = day.weekday()
        for p in senior:
            if p.id in unavailable:
                continue
            rows.add("wellness_checkins", player_id=p.id, checkin_date=day,
                     sleep_hours=round(g.between(6, 9), 1), sleep_quality=g.rng.randint(2, 5),
                     fatigue=g.rng.randint(1, 3) if p.id in spiking and offset >= 35 else g.rng.randint(3, 5),
                     soreness=g.rng.randint(2, 5), mood=g.rng.randint(3, 5), stress=g.rng.randint(2, 5))
        if weekday == 6:
            continue  # rest day
        kind = "recovery" if weekday == 0 else ("gym" if weekday == 3 else "training")
        session_id = g.id()
        duration = {"recovery": 45, "gym": 60, "training": 90}[kind]
        starts = at(day, 10)
        rows.add("training_sessions", id=session_id, organisation_id=org, team_id=own_team, starts_at=starts,
                 duration_minutes=duration, kind=kind, focus=None,
                 planned_intensity={"recovery": "low", "gym": "moderate", "training": g.pick(("moderate", "high"))}[kind])
        event_id = g.id()
        rows.add("calendar_events", id=event_id, organisation_id=org, team_id=own_team, title=f"{kind.title()} session",
                 kind="training", starts_at=starts, ends_at=starts + timedelta(minutes=duration),
                 location="Training ground", match_id=None, training_session_id=session_id)
        rows.add("facility_bookings", id=g.id(), facility_id=facility_ids["gym"] if kind == "gym" else training_facility,
                 starts_at=starts, ends_at=starts + timedelta(minutes=duration), purpose=f"First-team {kind}",
                 booked_by=coach, external_party=None)
        for p in senior:
            if p.id in unavailable:
                rows.add("attendance", event_id=event_id, player_id=p.id, user_id=None, status="excused",
                         recorded_at=datetime.now(timezone.utc))
                continue
            rpe = {"recovery": 3, "gym": 5, "training": 6}[kind] + g.rng.gauss(0, 1)
            minutes = duration
            if p.id in spiking and offset >= 35:
                rpe += 2.5
                minutes = round(duration * 1.3)
            if p.id in modified and offset >= 39:
                minutes = round(duration * 0.5)
            rows.add("session_loads", session_id=session_id, player_id=p.id, participated=True, minutes=minutes,
                     rpe=round(min(max(rpe, 1), 10), 1), external_load=external_load(g, sport_id, p.role, kind, minutes))
            rows.add("attendance", event_id=event_id, player_id=p.id, user_id=None,
                     status="late" if g.chance(0.03) else "present", recorded_at=datetime.now(timezone.utc))
        if weekday == 1:
            meeting = g.id()
            m_start = at(day, 14)
            rows.add("calendar_events", id=meeting, organisation_id=org, team_id=None, title="Weekly staff meeting",
                     kind="meeting", starts_at=m_start, ends_at=m_start + timedelta(hours=1), location="Analysis room",
                     match_id=None, training_session_id=None)
            for user_list in staff.values():
                for user_id in user_list:
                    rows.add("attendance", event_id=meeting, player_id=None, user_id=user_id,
                             status="present" if g.chance(0.9) else "excused", recorded_at=datetime.now(timezone.utc))

    # Development goals and assessments.
    for p in g.rng.sample(senior, 6):
        key = sport["comparisonMetrics"][p.role][0]
        rows.add("development_goals", id=g.id(), organisation_id=org, player_id=p.id,
                 title=f"Improve {metric_defs[key]['label'].lower()}", metric_key=key, baseline=None, target=None,
                 due_on=as_of + timedelta(days=120), status="active", owner_id=coach, created_at=datetime.now(timezone.utc))
    for pid, role in academy_players:
        rows.add("development_goals", id=g.id(), organisation_id=org, player_id=pid, title="Complete strength foundation block",
                 metric_key=None, baseline=None, target=None, due_on=as_of + timedelta(days=90), status="active",
                 owner_id=staff["head_coach"][-1], created_at=datetime.now(timezone.utc))
    for p_id in [p.id for p in senior] + [pid for pid, _ in academy_players]:
        for months_ago in (0, 2):
            rows.add("assessments", id=g.id(), organisation_id=org, player_id=p_id,
                     assessed_on=as_of - timedelta(days=30 * months_ago + g.rng.randint(0, 5)), kind="physical",
                     results={"sprint_30m_s": round(g.between(3.9, 4.6), 2), "cmj_cm": round(g.between(32, 52), 1)},
                     notes=None, assessor_id=performance)

    # Tasks and announcements -----------------------------------------------------------
    task_templates = (
        ("Prepare opponent report", "analyst"), ("Update shortlist video", "analyst"), ("Contract renewal proposal", "sporting_director"),
        ("Medical screening schedule", "medical"), ("Return-to-play plan review", "medical"), ("Monthly budget review", "finance"),
        ("Sponsor activation plan", "executive"), ("Academy parents' evening", "head_coach"), ("Scout regional fixtures", "scout"),
        ("Load plan for next microcycle", "performance"),
    )
    for title, role in task_templates:
        rows.add("tasks", id=g.id(), organisation_id=org, title=title, description=None, assignee_id=g.pick(staff[role]),
                 player_id=None, due_on=as_of + timedelta(days=g.rng.randint(-3, 21)),
                 status=g.pick(("todo", "todo", "in_progress", "done")), priority=g.pick(("normal", "normal", "high")),
                 created_by=director, created_at=datetime.now(timezone.utc))
    for title, audience in (("Pre-season schedule published", "all_staff"), ("New wellness check-in app", "players"),
                            ("Academy trials next month", "academy")):
        rows.add("announcements", id=g.id(), organisation_id=org, title=title, body="Details in the shared calendar.",
                 audience=audience, published_at=datetime.now(timezone.utc), author_id=director)

    # Commercial (Stage 6) ---------------------------------------------------------------
    deals = []
    for name, industry, tier, value in (
        ("Northwind Logistics", "logistics", "principal", 0.12), ("Brightpath Energy", "energy", "kit", 0.06),
        ("Copperleaf Bank", "finance", "official_partner", 0.03), ("Velo Sports Nutrition", "nutrition", "supplier", 0.01),
        ("Greenfield Motors", "automotive", "official_partner", 0.025), ("Learnwell Education", "education", "academy", 0.005),
    ):
        sponsor_id = g.id()
        rows.add("sponsors", id=sponsor_id, organisation_id=org, name=name, industry=industry,
                 contact_name=g.name(), contact_email=f"partnerships@{name.split()[0].lower()}.example")
        deal_id = g.id()
        annual = money(wage_bill * value)
        rows.add("sponsorship_deals", id=deal_id, sponsor_id=sponsor_id, tier=tier, starts_on=date(fy - 1, 7, 1),
                 ends_on=date(fy + g.rng.randint(1, 3), 6, 30), currency=cur, annual_value=annual,
                 deliverables=[{"item": "logo placement"}, {"item": "hospitality", "per": "home game"}], status="active")
        deals.append((deal_id, name, annual))
        for quarter_month in (1, 4, 7, 10):
            day = date(fy, quarter_month, 15)
            if day <= as_of:
                rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=day, fiscal_year=fy,
                         category="sponsorship_income", currency=cur, amount=money(annual / 4),
                         description=f"{name} quarterly instalment", counterparty=name, player_id=None, contract_id=None)
    for name, kind, units, price in (("Pitch-side LED", "led_board", 40, 0.0008), ("Stadium static boards", "static_board", 60, 0.0003),
                                     ("Training kit sleeve", "training_kit", 1, 0.004), ("Matchday programme", "matchday_programme", 20, 0.0001),
                                     ("Website and app banners", "digital", 30, 0.0002), ("Executive boxes", "hospitality", 12, 0.0006)):
        inv_id = g.id()
        rate = money(wage_bill * price)
        rows.add("ad_inventory", id=inv_id, organisation_id=org, name=name, kind=kind, units_available=units,
                 rate_card_price=rate, currency=cur)
        for _ in range(g.rng.randint(1, 3)):
            booked_units = g.rng.randint(1, max(units // 3, 1))
            deal = g.pick(deals)
            booking_start = date(fy, g.rng.randint(1, max(as_of.month, 1)), 1)
            price_paid = money(rate * booked_units * g.between(0.75, 1.0))
            rows.add("ad_bookings", id=g.id(), inventory_id=inv_id, deal_id=deal[0] if g.chance(0.5) else None,
                     advertiser=deal[1], starts_on=booking_start, ends_on=booking_start + timedelta(days=g.rng.randint(30, 180)),
                     units=booked_units, price=price_paid)
            rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=booking_start, fiscal_year=fy,
                     category="advertising_income", currency=cur, amount=price_paid, description=f"{name} booking",
                     counterparty=deal[1], player_id=None, contract_id=None)

    stadium = facility_ids["stadium"]
    home_matches = [m for m in lg.matches if m["home_team_id"] == own_team]
    for m in home_matches:
        attendance = round(cfg.stadium_capacity * g.between(0.6, 0.98))
        ticket = money(attendance * cfg.ticket_price * g.between(0.9, 1.1))
        event_day = m["kickoff_at"].date()
        rows.add("stadium_events", id=g.id(), organisation_id=org, facility_id=stadium, match_id=m["id"], event_date=event_day,
                 kind="home_match", attendance=attendance, capacity=cfg.stadium_capacity, currency=cur, ticket_revenue=ticket,
                 hospitality_revenue=money(ticket * 0.25), concessions_revenue=money(attendance * cfg.ticket_price * 0.3),
                 operating_cost=money(ticket * 0.35))
        rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=event_day, fiscal_year=event_day.year,
                 category="matchday_income", currency=cur, amount=money(ticket * 1.55), description="Home game revenue",
                 counterparty=None, player_id=None, contract_id=None)
        rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=event_day, fiscal_year=event_day.year,
                 category="operations", currency=cur, amount=-money(ticket * 0.35), description="Home game operating cost",
                 counterparty=None, player_id=None, contract_id=None)
    for title, kind in (("Summer concert", "concert"), ("Business conference", "conference")):
        day = as_of - timedelta(days=g.rng.randint(20, 120))
        revenue = money(cfg.stadium_capacity * cfg.ticket_price * 0.4)
        rows.add("stadium_events", id=g.id(), organisation_id=org, facility_id=stadium, match_id=None, event_date=day, kind=kind,
                 attendance=round(cfg.stadium_capacity * 0.7), capacity=cfg.stadium_capacity, currency=cur,
                 ticket_revenue=0, hospitality_revenue=0, concessions_revenue=money(revenue * 0.2), operating_cost=money(revenue * 0.3))
        rows.add("facility_bookings", id=g.id(), facility_id=stadium, starts_at=at(day, 17), ends_at=at(day, 23),
                 purpose=title, booked_by=staff["executive"][0], external_party=f"{title} organiser")
        rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=day, fiscal_year=day.year,
                 category="stadium_hire_income", currency=cur, amount=revenue, description=title,
                 counterparty=f"{title} organiser", player_id=None, contract_id=None)

    # Budgets and monthly costs ------------------------------------------------------------
    budget_lines = {
        "player_wages": wage_bill * 1.03, "staff_wages": staff_salaries * 1.05, "transfers": transfer_budget,
        "operations": wage_bill * 0.08, "facilities": wage_bill * 0.05, "travel": wage_bill * 0.03,
        "medical": wage_bill * 0.015, "academy": wage_bill * 0.02, "marketing": wage_bill * 0.015,
    }
    for category, amount in budget_lines.items():
        rows.add("budgets", organisation_id=org, fiscal_year=fy, category=category, currency=cur, amount=money(amount))
    for month in range(1, as_of.month + 1):
        day = date(fy, month, 25)
        if day > as_of:
            break
        for category, share, description in (
            ("player_wages", wage_bill / 12, "Player payroll"), ("staff_wages", staff_salaries / 12, "Staff payroll"),
            ("facilities", budget_lines["facilities"] / 12 * g.between(0.8, 1.2), "Facilities and maintenance"),
            ("travel", budget_lines["travel"] / 12 * g.between(0.6, 1.4), "Team travel"),
            ("medical", budget_lines["medical"] / 12 * g.between(0.7, 1.3), "Medical services"),
            ("academy", budget_lines["academy"] / 12 * g.between(0.8, 1.2), "Academy operations"),
            ("marketing", budget_lines["marketing"] / 12 * g.between(0.5, 1.5), "Marketing"),
        ):
            rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=day, fiscal_year=fy,
                     category=category, currency=cur, amount=-money(share), description=description,
                     counterparty=None, player_id=None, contract_id=None)
        rows.add("financial_transactions", id=g.id(), organisation_id=org, occurred_on=day, fiscal_year=fy,
                 category="broadcast_income", currency=cur, amount=money(wage_bill * 0.045), description="Central broadcast distribution",
                 counterparty=cfg.league, player_id=None, contract_id=None)

    # Payroll: monthly runs with payslips for players and staff --------------------------
    staff_rows = [r for r in rows.tables["staff_profiles"] if r["organisation_id"] == org]
    for month in range(1, as_of.month + 1):
        period_start = date(fy, month, 1)
        period_end = (date(fy + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
        if period_end > as_of:
            break
        run_id = g.id()
        rows.add("payroll_runs", id=run_id, organisation_id=org, period_start=period_start, period_end=period_end,
                 currency=cur, status="paid", approved_by=staff["finance"][0], paid_on=date(fy, month, 25))
        for p in own:
            contract = contract_by_player[p.id]
            bonus_rule = next((c for c in contract["clauses"] if c["type"] == "appearance_bonus"), None)
            appearances = g.rng.randint(0, 4) if bonus_rule else 0
            bonus = money(appearances * bonus_rule["amount"]) if bonus_rule else 0
            rows.add("payslips", id=g.id(), payroll_run_id=run_id, player_id=p.id, user_id=None, contract_id=contract["id"],
                     basic_pay=money(contract["annual_salary"] / 12), bonuses=bonus,
                     bonus_detail=[{"type": "appearance_bonus", "count": appearances, "amount": bonus}] if bonus else [])
        for sp in staff_rows:
            rows.add("payslips", id=g.id(), payroll_run_id=run_id, player_id=None, user_id=sp["user_id"], contract_id=None,
                     basic_pay=money(sp["annual_salary"] / 12), bonuses=0, bonus_detail=[])

    # Messages between staff ------------------------------------------------------------
    for subject, people, player, lines in (
        ("Return-to-play plan", [medical, performance, coach], next(iter(unavailable)), (
            "Scan results are back; plan attached to the medical record.",
            "Can we build in a modified week before full training?",
            "Agreed. I'll update the load plan.")),
        ("Recruitment shortlist", [director, scout_ids[0], analyst], reports[0][1].id, (
            "Clips from the last two matches are in the shortlist playlist.",
            "Strong on the metrics we weight most; worth a live watch.",
            "Booking travel for next weekend.")),
        ("Monthly budget check", [staff["finance"][0], director, staff["executive"][0]], None, (
            "Travel is running ahead of budget this quarter.",
            "Mostly cup fixtures; should settle next month.")),
    ):
        thread_id = g.id()
        rows.add("message_threads", id=thread_id, organisation_id=org, subject=subject, player_id=player,
                 created_by=people[0], created_at=datetime.now(timezone.utc))
        for user_id in people:
            rows.add("message_participants", thread_id=thread_id, user_id=user_id, last_read_at=None)
        for i, body in enumerate(lines):
            rows.add("messages", id=g.id(), thread_id=thread_id, sender_id=people[i % len(people)], body=body,
                     sent_at=at(as_of - timedelta(days=len(lines) - i), 9 + i))

    # Decisions and reviewed outcomes ------------------------------------------------------
    renewal_player = max(own, key=lambda p: p.quality)
    for kind, title, player_id, days_ago, rationale, rating in (
        ("renewal", "Extend contract of top performer", renewal_player.id, 300,
         "Highest role performance score in the squad; contract expiring.", 4),
        ("signing", f"Sign {signing.name}", signing.id, 120, "Top scouting rating for the role and within the wage budget.", None),
        ("return_to_play", "Phased return after injury", next(iter(unavailable)), 10,
         "Medical team cleared modified training; workload ramped over two weeks.", None),
        ("commercial", "Renew principal sponsor", None, 200, "Committed income for three seasons at a higher annual value.", 5),
    ):
        decision_id = g.id()
        decided_on = as_of - timedelta(days=days_ago)
        rows.add("decisions", id=decision_id, organisation_id=org, kind=kind, title=title, player_id=player_id,
                 recommendation_id=None, scenario_id=scenario_id if kind == "signing" else None, decided_on=decided_on,
                 decided_by=director, rationale=rationale, expected_outcome={"review_after_days": 180},
                 review_on=decided_on + timedelta(days=180), status="reviewed" if rating else "open")
        if rating:
            rows.add("decision_outcomes", id=g.id(), decision_id=decision_id, reviewed_on=decided_on + timedelta(days=180),
                     reviewer_id=staff["executive"][0], rating=rating, actual={"summary": "Met expectations"},
                     lessons="Keep reviewing similar decisions at six months.")


def external_load(g: Gen, sport_id: str, role: str, kind: str, minutes: int) -> dict[str, Any]:
    if kind != "training":
        return {}
    if sport_id == "soccer":
        return {"distance_m": round(minutes * g.between(70, 95)), "high_speed_m": round(minutes * g.between(4, 9))}
    if sport_id == "basketball":
        return {"accelerations": round(minutes * g.between(1.5, 3)), "jumps": round(minutes * g.between(0.5, 1.2))}
    if sport_id == "ice_hockey":
        return {"skating_distance_m": round(minutes * g.between(45, 70))}
    if sport_id == "american_football":
        return {"distance_m": round(minutes * g.between(40, 70)), "contact_reps": g.rng.randint(0, 25)}
    if sport_id == "baseball":
        return {"throws": g.rng.randint(20, 60)} if "pitcher" not in role else {"pitches": g.rng.randint(15, 40)}
    if sport_id == "cricket":
        return {"balls_bowled": g.rng.randint(18, 48)} if "bowler" in role else {"balls_faced": g.rng.randint(60, 150)}
    return {}


# ---------------------------------------------------------------------------


def generate(sports: Iterable[str] | None = None, seed: int = 7, as_of: date | None = None) -> Rows:
    g = Gen(seed, as_of or date.today())
    rows = Rows()
    for sport_id in sports or LEAGUES:
        league = build_league(g, rows, sport_id)
        build_club(g, rows, league)
    return rows


def load_mock_data(conn: psycopg.Connection, sports: Iterable[str] | None = None, seed: int = 7,
                   as_of: date | None = None) -> dict[str, int]:
    """Writes demo data into an empty database (no organisations yet) in one transaction."""
    with conn.cursor() as cur:
        cur.execute("select count(*) from organisations")
        if cur.fetchone()[0]:
            raise RuntimeError("Database already has organisations; load demo data into a fresh database.")
    rows = generate(sports, seed, as_of)
    counts = rows.write(conn)
    conn.commit()
    return counts


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Load fictional demo data into the database named by DATABASE_URL.")
    parser.add_argument("--sport", action="append", choices=sorted(LEAGUES), help="Limit to these sports (repeatable).")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="Date the demo club is 'today' (default: today).")
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit("DATABASE_URL is not set")
    with psycopg.connect(database_url) as conn:
        counts = load_mock_data(conn, args.sport, args.seed, args.as_of)
    width = max(map(len, counts))
    for table, n in counts.items():
        print(f"{table:<{width}}  {n:>7,}")
