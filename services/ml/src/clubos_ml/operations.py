"""Club-level jobs: role performance scores, financial forecasts and multi-year plans,
and generated player performance reports."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .pipeline import Sample, create_model_run

# ---------------------------------------------------------------------------
# Role performance scores (inputs to ROI views and reports)
# ---------------------------------------------------------------------------


def run_performance_scores(conn: psycopg.Connection, sport: dict[str, Any], samples: list[Sample]) -> int:
    scored = [s for s in samples if s.percentiles]
    if not scored:
        return 0
    run_id = create_model_run(
        conn, "performance_score", "0.1.0", sport["id"],
        {"intended_use": "A single 0–100 summary of a player's season in their role, for ROI and reports.",
         "method": "Mean direction-aware percentile of the role's comparison metrics within league, season and role.",
         "limitations": ["Equal weight per metric; club style weights are applied only in tactical fit.",
                         "No league-strength adjustment."]},
        {},
    )
    with conn.cursor() as cur:
        cur.executemany(
            "insert into player_performance_scores (player_id, season_id, model_run_id, role_key, score, low_sample, percentiles)"
            " values (%s, %s, %s, %s, %s, %s, %s)",
            [(s.player_id, s.season_id, run_id, s.role, round(s.performance_score, 2), s.low_sample, Jsonb(s.percentiles))
             for s in scored],
        )
    return len(scored)


# ---------------------------------------------------------------------------
# Financial forecasts and plans
# ---------------------------------------------------------------------------

CONTRACTED = {"player_wages", "sponsorship_income"}
PLAN_ASSUMPTIONS = {"wage_inflation": 0.04, "staff_wage_inflation": 0.03, "cost_inflation": 0.03,
                    "commercial_growth": 0.05, "sponsor_renewal_rate": 0.8}


def _overlap_fraction(start: date, end: date, window_start: date, window_end: date) -> float:
    days = (min(end, window_end) - max(start, window_start)).days + 1
    return max(days, 0) / 365.0


def run_financial_forecasts(conn: psycopg.Connection, as_of: date) -> int:
    """Full-year projection per category for the current fiscal year, then a three-year plan.
    Amounts in financial_forecasts are positive; the category says whether it is income or cost."""
    run_id = create_model_run(
        conn, "financial_forecast", "0.1.0", None,
        {"intended_use": "Where the year will land against budget, and what the next three years look like.",
         "method": "Contracted categories (player wages, sponsorship) are projected from active contracts and deals "
                   "pro rata; other categories from the year-to-date monthly run rate. The plan adds committed "
                   "amounts for future years plus stated assumptions for what is not yet contracted.",
         "assumptions": PLAN_ASSUMPTIONS,
         "limitations": ["Run rates ignore seasonality.", "Transfer activity is planned via budget scenarios, not here."]},
        {},
    )
    fy = as_of.year
    year_end = date(fy, 12, 31)
    remaining_from = as_of + timedelta(days=1)
    months_elapsed = max(as_of.month - 1 + as_of.day / 31, 1)
    months_left = max((year_end - as_of).days / 30.44, 0)
    written = 0
    for org_id, currency in conn.execute(
            "select distinct organisation_id, currency from budgets where fiscal_year = %s", (fy,)).fetchall():
        actuals = dict(conn.execute(
            "select category, sum(amount) from financial_transactions"
            " where organisation_id = %s and fiscal_year = %s and currency = %s group by 1",
            (org_id, fy, currency)).fetchall())
        budgets = dict(conn.execute(
            "select category, amount from budgets where organisation_id = %s and fiscal_year = %s", (org_id, fy)).fetchall())
        contracts = conn.execute(
            "select starts_on, ends_on, annual_salary from contracts where organisation_id = %s and status = 'active' and currency = %s",
            (org_id, currency)).fetchall()
        deals = conn.execute(
            "select d.starts_on, d.ends_on, d.annual_value from sponsorship_deals d join sponsors s on s.id = d.sponsor_id"
            " where s.organisation_id = %s and d.status = 'active' and d.currency = %s", (org_id, currency)).fetchall()
        full_year: dict[str, float] = {}
        for category in sorted(set(actuals) | set(budgets)):
            actual = abs(float(actuals.get(category, 0)))
            if category == "player_wages":
                remaining = sum(float(s) * _overlap_fraction(a, b, remaining_from, year_end) for a, b, s in contracts)
                basis, spread = "contracted", 0.03
            elif category == "sponsorship_income":
                remaining = sum(float(v) * _overlap_fraction(a, b, remaining_from, year_end) for a, b, v in deals)
                basis, spread = "contracted", 0.03
            else:
                remaining = actual / months_elapsed * months_left
                basis, spread = "run_rate", 0.15
            projected = actual + remaining
            full_year[category] = projected
            budget = budgets.get(category)
            conn.execute(
                "insert into financial_forecasts (organisation_id, model_run_id, as_of, fiscal_year, category, currency,"
                " actual_to_date, projected_remaining, projected_full_year, projected_low, projected_high, budget, basis)"
                " values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (org_id, run_id, as_of, fy, category, currency, round(actual, 2), round(remaining, 2), round(projected, 2),
                 round(actual + remaining * (1 - spread), 2), round(actual + remaining * (1 + spread), 2),
                 float(budget) if budget is not None else None, basis))
            written += 1
        written += _write_plan(conn, run_id, org_id, currency, fy, full_year, contracts, deals)
    return written


def _write_plan(conn: psycopg.Connection, run_id: Any, org_id: Any, currency: str, fy: int,
                full_year: dict[str, float], contracts: list, deals: list) -> int:
    plan_id = conn.execute(
        "insert into financial_plans (organisation_id, model_run_id, name, first_year, years, currency, assumptions)"
        " values (%s, %s, %s, %s, 3, %s, %s) returning id",
        (org_id, run_id, f"Three-year plan {fy + 1}–{fy + 3}", fy + 1, currency, Jsonb(PLAN_ASSUMPTIONS))).fetchone()[0]
    a = PLAN_ASSUMPTIONS
    rows = []
    for n, year in enumerate(range(fy + 1, fy + 4), start=1):
        start, end = date(year, 1, 1), date(year, 12, 31)
        for category, base in full_year.items():
            is_income = category.endswith("_income")
            committed = 0.0
            if category == "player_wages":
                committed = sum(float(s) * _overlap_fraction(x, y, start, end) for x, y, s in contracts)
                target = base * (1 + a["wage_inflation"]) ** n  # squad cost kept at today's level, plus inflation
                amount = max(target, committed)
            elif category == "sponsorship_income":
                committed = sum(float(v) * _overlap_fraction(x, y, start, end) for x, y, v in deals)
                expiring = max(base - committed, 0)
                amount = committed + expiring * a["sponsor_renewal_rate"] * (1 + a["commercial_growth"]) ** n
            elif category == "staff_wages":
                amount = base * (1 + a["staff_wage_inflation"]) ** n
            elif category == "transfers":
                continue  # planned through budget scenarios
            elif is_income:
                amount = base * (1 + a["commercial_growth"]) ** n
            else:
                amount = base * (1 + a["cost_inflation"]) ** n
            sign = 1 if is_income else -1
            rows.append((plan_id, year, category, round(sign * amount, 2), round(sign * committed, 2)))
    with conn.cursor() as cur:
        cur.executemany(
            "insert into financial_plan_lines (plan_id, fiscal_year, category, amount, committed) values (%s, %s, %s, %s, %s)",
            rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Player performance reports
# ---------------------------------------------------------------------------


def run_player_reports(conn: psycopg.Connection, as_of: date, sports: dict[str, dict[str, Any]]) -> int:
    run_id = create_model_run(
        conn, "player_report", "0.1.0", None,
        {"intended_use": "A one-page summary for coaches and the player, built only from stored data and model outputs.",
         "method": "Template text over the latest performance score, forecasts, workload indicators, availability, "
                   "development goals and assessments. Every item names its source table.",
         "limitations": ["Descriptive only; no free-text generation, so nothing is stated that the data does not show."]},
        {},
    )
    period_start = as_of - timedelta(days=42)
    squad = conn.execute(
        "select s.organisation_id, s.player_id, p.full_name, p.sport_id from squad_members s join players p on p.id = s.player_id"
        " where s.status = 'first_team' and s.left_on is null").fetchall()
    written = 0
    for org_id, player_id, name, sport_id in squad:
        metrics = {m["key"]: m["label"] for m in sports[sport_id]["metrics"]}
        sections, highlights = [], []

        score = conn.execute(
            "select ps.score, ps.role_key, se.label, ps.low_sample, ps.percentiles from player_performance_scores ps"
            " join seasons se on se.id = ps.season_id join model_runs r on r.id = ps.model_run_id"
            " where ps.player_id = %s order by se.starts_on desc nulls last, r.trained_at desc limit 1",
            (player_id,)).fetchone()
        if score:
            items = [{"label": "Role performance score", "value": float(score[0]), "season": score[2],
                      "low_sample": score[3], "source": "player_performance_scores"}]
            if score[4]:
                ranked = sorted(score[4].items(), key=lambda kv: -kv[1])
                items += [{"label": f"Strength: {metrics.get(k, k)}", "percentile": v, "source": "player_performance_scores"}
                          for k, v in ranked[:2]]
                items += [{"label": f"To develop: {metrics.get(k, k)}", "percentile": v, "source": "player_performance_scores"}
                          for k, v in ranked[-1:]]
                best_key, best = ranked[0]
                label = metrics.get(best_key, best_key).lower()
                if best >= 60:
                    highlights.append(f"strongest on {label} (percentile {best:.0f} in role)")
                elif best < 50:
                    highlights.append(f"below the role median on every compared metric; best is {label} (percentile {best:.0f})")
                else:
                    highlights.append(f"around the role median; best is {label} (percentile {best:.0f})")
            sections.append({"title": f"Season performance ({score[2]})", "items": items})

        forecasts = conn.execute(
            "select f.metric_key, f.forecast, f.forecast_low, f.forecast_high, f.evidence_weight, f.season_label"
            " from performance_forecasts f join model_runs r on r.id = f.model_run_id"
            " where f.player_id = %s order by r.trained_at desc, f.evidence_weight desc limit 3", (player_id,)).fetchall()
        if forecasts:
            sections.append({"title": f"Next season outlook ({forecasts[0][5]})", "items": [
                {"label": metrics.get(k, k), "forecast": float(f), "range": [float(lo), float(hi)],
                 "evidence_weight": float(w), "source": "performance_forecasts"} for k, f, lo, hi, w, _ in forecasts]})

        workload = conn.execute(
            "select as_of, acwr, monotony, wellness_score, flags from workload_indicators where player_id = %s"
            " order by as_of desc limit 1", (player_id,)).fetchone()
        if workload:
            sections.append({"title": "Workload indicators (for performance staff)", "items": [
                {"label": "Acute:chronic workload ratio", "value": float(workload[1]) if workload[1] is not None else None,
                 "as_of": str(workload[0]), "source": "workload_indicators"},
                {"label": "Wellness (1–5)", "value": float(workload[3]) if workload[3] is not None else None,
                 "source": "workload_indicators"},
                {"label": "Indicators flagged", "value": list(workload[4]), "source": "workload_indicators"}]})
            if workload[4]:
                highlights.append("workload indicators flagged for review: " + ", ".join(f.replace("_", " ") for f in workload[4]))

        availability = conn.execute(
            "select status, reason_category, expected_return_on from availability_status where player_id = %s"
            " and starts_on <= %s and (ends_on is null or ends_on >= %s) order by starts_on desc limit 1",
            (player_id, as_of, as_of)).fetchone()
        sections.append({"title": "Availability", "items": [{
            "label": "Status", "value": availability[0] if availability else "available",
            "reason_category": availability[1] if availability else None,
            "expected_return_on": str(availability[2]) if availability and availability[2] else None,
            "source": "availability_status"}]})
        if availability and availability[0] != "available":
            highlights.append(f"currently {availability[0].replace('_', ' ')}")

        goals = conn.execute(
            "select title, status, due_on from development_goals where player_id = %s and status = 'active'", (player_id,)).fetchall()
        if goals:
            sections.append({"title": "Development goals", "items": [
                {"label": t, "status": s, "due_on": str(d) if d else None, "source": "development_goals"} for t, s, d in goals]})

        tests = conn.execute(
            "select assessed_on, results from assessments where player_id = %s and kind = 'physical' order by assessed_on desc limit 2",
            (player_id,)).fetchall()
        if tests:
            latest = tests[0][1]
            previous = tests[1][1] if len(tests) > 1 else {}
            sections.append({"title": "Physical testing", "items": [
                {"label": key, "value": value, "previous": previous.get(key), "source": "assessments"}
                for key, value in latest.items()]})

        summary = f"{name}: " + ("; ".join(highlights) if highlights else "no notable changes in this period") + "."
        conn.execute(
            "insert into player_reports (organisation_id, player_id, model_run_id, period_start, period_end, summary, sections)"
            " values (%s, %s, %s, %s, %s, %s, %s)",
            (org_id, player_id, run_id, period_start, as_of, summary, Jsonb(sections)))
        written += 1
    return written
