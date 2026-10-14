"""Batch jobs that read the database, compute model outputs and write them back.

Each job records a model run with a model card, so every number shown to staff can be
traced to the model, version and data that produced it.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import numpy as np
import psycopg
from psycopg.types.json import Jsonb

from .stats import cross_validate, fit_ridge, next_season_label, normalise, percentile_rank, shrink, workload_indicator

INTERVAL_Z = 1.2816  # 80% interval
# Percentiles against fewer reference players than this are not meaningful.
MIN_POOL = 5


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


def load_sport(sport_id: str) -> dict[str, Any]:
    return json.loads((sports_dir() / sport_id.replace("_", "-") / "sport.json").read_text())


def exposure_for(sport: dict[str, Any], role: str) -> dict[str, Any]:
    return (sport.get("roleExposure") or {}).get(role, sport["exposure"])


@dataclass
class Sample:
    player_id: Any
    competition_id: Any
    season_id: Any
    season_label: str
    role: str
    exposure: float
    birth_date: date | None
    totals: dict[str, float | None]
    percentiles: dict[str, float] = field(default_factory=dict)
    values: dict[str, float] = field(default_factory=dict)
    low_sample: bool = False
    exposure_unit: str = ""

    @property
    def performance_score(self) -> float | None:
        return mean(self.percentiles.values()) if self.percentiles else None


def age_on(birth: date | None, on: date) -> float | None:
    return (on - birth).days / 365.25 if birth else None


def merge_team_rows(samples: list[Sample], metrics: dict[str, dict[str, Any]]) -> list[Sample]:
    """One sample per player and season. A player who moved teams mid-season has a row per
    team, merged like a stats site's combined line for a traded player:
    - only rows measured in the same exposure unit as the main row (the one with the most
      exposure) are combined, so kicks are never added to snaps;
    - counts are summed;
    - rates are weighted by their own denominator when the sport names one (metric
      "weightBy", e.g. completion % by pass attempts), otherwise by exposure."""
    grouped: dict[tuple[Any, Any], list[Sample]] = defaultdict(list)
    for s in samples:
        grouped[(s.player_id, s.season_id)].append(s)
    merged = []
    for group in grouped.values():
        main = max(group, key=lambda s: s.exposure)
        group = [s for s in group if s.exposure_unit == main.exposure_unit]
        if len(group) == 1:
            merged.append(main)
            continue
        totals: dict[str, float | None] = {}
        for key in {k for s in group for k in s.totals}:
            present = [s for s in group if s.totals.get(key) is not None]
            if not present:
                totals[key] = None
            elif metrics.get(key, {}).get("normalisation") == "rate":
                weight_by = metrics[key].get("weightBy")

                def weight(s: Sample) -> float:
                    return (s.totals.get(weight_by) or 0.0) if weight_by else s.exposure

                total_weight = sum(weight(s) for s in present)
                totals[key] = (sum(s.totals[key] * weight(s) for s in present) / total_weight if total_weight
                               else mean(s.totals[key] for s in present))
            else:
                totals[key] = sum(s.totals[key] for s in present)
        merged.append(Sample(main.player_id, main.competition_id, main.season_id, main.season_label, main.role,
                             sum(s.exposure for s in group), main.birth_date, totals, exposure_unit=main.exposure_unit))
    return merged


def latest_samples(conn: psycopg.Connection, sport: dict[str, Any]) -> list[Sample]:
    """Season stats from the latest season of each competition in the sport, with
    direction-aware percentiles computed within (season, role) among players with enough
    exposure, the same rule the web app uses."""
    rows = conn.execute(
        """
        with latest as (
          select distinct on (se.competition_id) se.id, se.competition_id, se.label
          from seasons se
          join competitions c on c.id = se.competition_id
          where c.sport_id = %s and exists (select 1 from player_season_stats s where s.season_id = se.id)
          order by se.competition_id, se.starts_on desc nulls last
        )
        select s.player_id, l.competition_id, l.id, l.label, s.role_key, s.exposure, p.birth_date,
               coalesce(jsonb_object_agg(v.metric_key, v.value) filter (where v.metric_key is not null), '{}'),
               s.exposure_unit
        from player_season_stats s
        join latest l on l.id = s.season_id
        join players p on p.id = s.player_id
        left join player_season_metric_values v on v.season_stats_id = s.id
        where s.role_key is not null and s.exposure is not null
        group by s.id, s.player_id, l.competition_id, l.id, l.label, s.role_key, s.exposure, p.birth_date, s.exposure_unit
        """,
        (sport["id"],),
    ).fetchall()
    metrics = {m["key"]: m for m in sport["metrics"]}
    samples = merge_team_rows([
        Sample(r[0], r[1], r[2], r[3], r[4], float(r[5]), r[6],
               {k: (float(v) if v is not None else None) for k, v in r[7].items()}, exposure_unit=r[8])
        for r in rows
    ], metrics)
    groups: dict[tuple[Any, str], list[Sample]] = defaultdict(list)
    for s in samples:
        groups[(s.season_id, s.role)].append(s)
    for (_, role), group in groups.items():
        unit = exposure_for(sport, role)
        for s in group:
            s.low_sample = s.exposure < unit["minimumForComparison"]
            for key in sport["comparisonMetrics"].get(role, []):
                value = normalise(s.totals.get(key), s.exposure, unit["per"], metrics[key]["normalisation"])
                if value is not None:
                    s.values[key] = value
        pool = [s for s in group if not s.low_sample]
        for key in sport["comparisonMetrics"].get(role, []):
            pool_values = [s.values[key] for s in pool if key in s.values]
            if len(pool_values) < MIN_POOL:
                continue
            for s in group:
                if key in s.values:
                    pct = percentile_rank(s.values[key], pool_values, metrics[key]["higherIsBetter"])
                    if pct is not None:
                        s.percentiles[key] = pct
    return samples


def create_model_run(conn: psycopg.Connection, name: str, version: str, sport_id: str | None,
                     card: dict[str, Any], metrics: dict[str, Any]) -> Any:
    return conn.execute(
        "insert into model_runs (model_name, model_version, sport_id, card, metrics) values (%s, %s, %s, %s, %s) returning id",
        (name, version, sport_id, Jsonb(card), Jsonb(metrics)),
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Valuation
# ---------------------------------------------------------------------------

VALUATION_CARD = {
    "intended_use": "A starting point for valuation discussions: a range, with its main drivers. Not a price to pay.",
    "method": "Ridge regression on log(value) using age, age squared, role performance score (mean percentile "
              "of the role's comparison metrics), playing-time share and role group. Fitted per competition.",
    "training_data": "Market transactions (fees or annual salaries per the sport's valuation basis) for players "
                     "with season stats in the same competition.",
    "limitations": [
        "Features come from the latest season, which may postdate older transactions.",
        "Undisclosed fees are excluded, which can bias toward publicised deals.",
        "Only players from competitions with enough market data are valued.",
        "Contract length, agent and club finances are not modelled.",
    ],
}


def _features(sample: Sample, role_groups: list[str], groups_by_role: dict[str, str], max_exposure: float,
              on: date) -> list[float] | None:
    age = age_on(sample.birth_date, on)
    score = sample.performance_score
    if age is None or score is None:
        return None
    group_flags = [1.0 if groups_by_role[sample.role] == g else 0.0 for g in role_groups[1:]]
    return [age, age * age, score, min(sample.exposure / max_exposure, 1.0) if max_exposure else 0.0, *group_flags]


def run_valuation(conn: psycopg.Connection, sport: dict[str, Any], samples: list[Sample], as_of: date) -> dict[Any, Any]:
    """Returns {player_id: valuation_id} for this run."""
    basis = sport["valuationBasis"]
    groups_by_role = {r["key"]: r["group"] for r in sport["roles"]}
    role_groups = sorted(set(groups_by_role.values()))
    names = ["age", "age_squared", "performance_score", "playing_time_share", *[f"group_{g}" for g in role_groups[1:]]]
    valuations: dict[Any, Any] = {}

    by_competition: dict[Any, list[Sample]] = defaultdict(list)
    for s in samples:
        by_competition[s.competition_id].append(s)

    for competition_id, comp_samples in by_competition.items():
        max_exposure: dict[str, float] = defaultdict(float)
        for s in comp_samples:
            max_exposure[s.role] = max(max_exposure[s.role], s.exposure)
        by_player = {s.player_id: s for s in comp_samples}
        transactions = conn.execute(
            "select player_id, occurred_on, currency, fee, annual_salary from market_transactions where player_id = any(%s)",
            (list(by_player),),
        ).fetchall()
        x, y, currencies = [], [], defaultdict(int)
        for player_id, occurred_on, currency, fee, salary in transactions:
            target = fee if basis == "transfer_fee" else salary
            if target is None or target <= 0:
                continue
            s = by_player[player_id]
            feats = _features(s, role_groups, groups_by_role, max_exposure[s.role], occurred_on)
            if feats is None:
                continue
            x.append(feats)
            y.append(math.log(float(target)))
            currencies[currency] += 1
        if len(y) < 30:
            continue
        currency = max(currencies, key=currencies.get)
        xa, ya = np.array(x), np.array(y)
        validation = cross_validate(xa, ya, names, z=INTERVAL_Z)
        model = fit_ridge(xa, ya, names)
        run_id = create_model_run(
            conn, "valuation_baseline", "0.1.0", sport["id"],
            {**VALUATION_CARD, "basis": basis, "currency": currency, "competition_id": str(competition_id),
             "features": names, "coefficients": dict(zip(names, map(float, model.coef)))},
            {"cv_mae_log": validation["mae"], "cv_interval_coverage_80": validation["interval_coverage"],
             "training_rows": validation["n"], "residual_sd_log": model.residual_sd},
        )
        for s in comp_samples:
            feats = _features(s, role_groups, groups_by_role, max_exposure[s.role], as_of)
            if feats is None:
                continue
            arr = np.array(feats)
            log_value = float(model.predict(arr[None, :])[0])
            contributions = model.contributions(arr)
            drivers = sorted(
                ({"feature": n, "effect_log": round(float(c), 3)} for n, c in zip(names, contributions)),
                key=lambda dct: -abs(dct["effect_log"]),
            )[:3]
            spread = INTERVAL_Z * model.residual_sd
            valuations[s.player_id] = conn.execute(
                "insert into player_valuations (player_id, model_run_id, as_of, basis, currency, value, value_low, value_high, drivers)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
                (s.player_id, run_id, as_of, basis, currency, round(math.exp(log_value), -2),
                 round(math.exp(log_value - spread), -2), round(math.exp(log_value + spread), -2), Jsonb(drivers)),
            ).fetchone()[0]
    return valuations


# ---------------------------------------------------------------------------
# Performance forecasts
# ---------------------------------------------------------------------------


def run_forecasts(conn: psycopg.Connection, sport: dict[str, Any], samples: list[Sample]) -> int:
    if not samples:
        return 0
    metrics = {m["key"]: m for m in sport["metrics"]}
    run_id = create_model_run(
        conn, "forecast_shrinkage", "0.1.0", sport["id"],
        {"intended_use": "Next-season expectation per comparison metric, with a range.",
         "method": "Shrink each player's rate toward the role average in proportion to playing time "
                   "(prior weight = the sport's minimum exposure for comparison), with a small age adjustment.",
         "limitations": ["No team-context or league-strength adjustment yet.", "Ranges assume role-level spread."]},
        {},
    )
    pools: dict[tuple[Any, str, str], list[float]] = defaultdict(list)
    for s in samples:
        if not s.low_sample:
            for key, value in s.values.items():
                pools[(s.season_id, s.role, key)].append(value)
    rows = []
    for s in samples:
        unit = exposure_for(sport, s.role)
        age = age_on(s.birth_date, date.today())
        for key, value in s.values.items():
            pool = pools.get((s.season_id, s.role, key), [])
            if len(pool) < 3:
                continue
            mu, sd = mean(pool), pstdev(pool)
            estimate, weight = shrink(value, s.exposure, mu, unit["minimumForComparison"])
            direction = 1 if metrics[key]["higherIsBetter"] else -1
            if age is not None and age < 23:
                estimate += direction * 0.15 * sd
            elif age is not None and age > 31:
                estimate -= direction * 0.15 * sd
            spread = INTERVAL_Z * sd * math.sqrt(1 - weight / 2)
            rows.append((s.player_id, run_id, next_season_label(s.season_label), s.role, key,
                         round(estimate, 4), round(estimate - spread, 4), round(estimate + spread, 4), round(weight, 3)))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into performance_forecasts (player_id, model_run_id, season_label, role_key, metric_key, forecast,"
            " forecast_low, forecast_high, evidence_weight) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
        )
    return len(rows)


# ---------------------------------------------------------------------------
# Tactical-fit recommendations
# ---------------------------------------------------------------------------


def run_recommendations(conn: psycopg.Connection, sport: dict[str, Any], samples: list[Sample],
                        valuations: dict[Any, Any], per_profile: int = 10) -> int:
    profiles = conn.execute(
        "select id, organisation_id, role_key, metric_weights from club_style_profiles where sport_id = %s",
        (sport["id"],),
    ).fetchall()
    if not profiles:
        return 0
    run_id = create_model_run(
        conn, "tactical_fit", "0.1.0", sport["id"],
        {"intended_use": "Rank players in a role against how the club wants that role played.",
         "method": "Weighted mean of the player's role percentiles using the club's style-profile weights; "
                   "weights of metrics a player lacks are re-normalised and the player is skipped if under half remain.",
         "limitations": ["Percentiles are within each player's own league-season; league strength is not adjusted."]},
        {},
    )
    written = 0
    for profile_id, org_id, role, weights in profiles:
        squad = {r[0] for r in conn.execute(
            "select player_id from squad_members where organisation_id = %s and left_on is null", (org_id,))}
        scored = []
        for s in samples:
            if s.role != role or s.player_id in squad:
                continue
            used = {k: float(w) for k, w in weights.items() if k in s.percentiles}
            if sum(used.values()) < 0.5 * sum(map(float, weights.values())):
                continue
            total_weight = sum(used.values())
            fit = sum(s.percentiles[k] * w for k, w in used.items()) / total_weight
            reasons = sorted(
                ({"metric": k, "percentile": s.percentiles[k], "weight": round(w / total_weight, 3)} for k, w in used.items()),
                key=lambda r: -r["percentile"] * r["weight"],
            )
            scored.append((fit, s, reasons))
        # Players with enough playing time first; low-sample players only fill remaining slots.
        scored.sort(key=lambda t: (t[1].low_sample, -t[0]))
        conn.execute(
            "delete from recommendations where style_profile_id = %s and status = 'new'", (profile_id,))
        for fit, s, reasons in scored[:per_profile]:
            clips = [r[0] for r in conn.execute(
                "select distinct c.id from clips c join videos v on v.id = c.video_id"
                " join clip_events ce on ce.clip_id = c.id join video_events e on e.id = ce.event_id"
                " where v.organisation_id = %s and e.player_id = %s", (org_id, s.player_id))]
            conn.execute(
                "insert into recommendations (organisation_id, player_id, role_key, style_profile_id, model_run_id,"
                " fit_score, valuation_id, reasons, evidence_clip_ids, low_sample)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (org_id, s.player_id, role, profile_id, run_id, round(fit, 2), valuations.get(s.player_id),
                 Jsonb(reasons), clips, s.low_sample),
            )
            written += 1
    return written


# ---------------------------------------------------------------------------
# Workload indicators
# ---------------------------------------------------------------------------


def run_workload(conn: psycopg.Connection, as_of: date | None = None) -> int:
    run_id = create_model_run(
        conn, "workload_indicators", "0.1.0", None,
        {"intended_use": "Monitoring indicators for qualified performance and medical staff.",
         "method": "Session RPE x minutes. Acute = last 7 days; chronic = 28-day weekly average; "
                   "monotony = 7-day mean / standard deviation; wellness = mean of the last 3 check-ins.",
         "not_for": "Diagnosing injury or predicting that a player will or will not get injured.",
         "flags": {"load_spike": "ACWR > 1.5", "underload": "ACWR < 0.8", "high_monotony": "monotony > 2.0",
                   "low_wellness": "wellness < 2.75 on a 1-5 scale"}},
        {},
    )
    players = conn.execute(
        "select distinct l.player_id, max(s.starts_at::date) over (partition by s.organisation_id)"
        " from session_loads l join training_sessions s on s.id = l.session_id"
    ).fetchall()
    written = 0
    for player_id, org_last_day in players:
        day = as_of or org_last_day
        start = day - timedelta(days=27)
        loads = dict(conn.execute(
            "select s.starts_at::date, sum(l.session_load) from session_loads l join training_sessions s on s.id = l.session_id"
            " where l.player_id = %s and s.starts_at::date between %s and %s group by 1",
            (player_id, start, day)).fetchall())
        daily = [float(loads.get(start + timedelta(days=i), 0) or 0) for i in range(28)]
        wellness = [float(r[0]) for r in conn.execute(
            "select (coalesce(sleep_quality, 3) + coalesce(fatigue, 3) + coalesce(soreness, 3) + coalesce(mood, 3)"
            " + coalesce(stress, 3)) / 5.0 from wellness_checkins where player_id = %s and checkin_date <= %s"
            " order by checkin_date desc limit 3", (player_id, day))]
        ind = workload_indicator(daily, wellness)
        conn.execute(
            "insert into workload_indicators (player_id, model_run_id, as_of, acute_load, chronic_load, acwr, monotony,"
            " wellness_score, flags) values (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " on conflict (player_id, as_of) do update set model_run_id = excluded.model_run_id,"
            " acute_load = excluded.acute_load, chronic_load = excluded.chronic_load, acwr = excluded.acwr,"
            " monotony = excluded.monotony, wellness_score = excluded.wellness_score, flags = excluded.flags",
            (player_id, run_id, day, ind.acute_load, ind.chronic_load, ind.acwr, ind.monotony, ind.wellness_score, ind.flags),
        )
        written += 1
    return written


def run_all(conn: psycopg.Connection, as_of: date | None = None) -> dict[str, int]:
    from .analytics import run_formations, run_units
    from .operations import run_financial_forecasts, run_performance_scores, run_player_reports

    today = as_of or date.today()
    summary: dict[str, int] = defaultdict(int)
    sports = {}
    for (sport_id,) in conn.execute("select distinct sport_id from competitions order by 1").fetchall():
        sport = sports[sport_id] = load_sport(sport_id)
        samples = latest_samples(conn, sport)
        summary["performance_scores"] += run_performance_scores(conn, sport, samples)
        valuations = run_valuation(conn, sport, samples, today)
        summary["valuations"] += len(valuations)
        summary["forecasts"] += run_forecasts(conn, sport, samples)
        summary["recommendations"] += run_recommendations(conn, sport, samples, valuations)
        summary["unit_stats"] += run_units(conn, sport)
        summary["formations"] += run_formations(conn, sport)
        conn.commit()
    summary["workload_indicators"] = run_workload(conn, as_of)
    summary["financial_forecast_rows"] = run_financial_forecasts(conn, today)
    conn.commit()
    summary["player_reports"] = run_player_reports(conn, today, sports)
    conn.commit()
    return dict(summary)
