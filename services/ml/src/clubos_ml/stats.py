"""Pure functions shared by the models. No database access here, so they are easy to test."""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


def percentile_rank(value: float, pool: Sequence[float], higher_is_better: bool) -> float | None:
    """Direction-aware percentile (0–100, mid-rank for ties). Same rule as packages/core."""
    if not pool:
        return None
    below = sum(1 for v in pool if (v < value if higher_is_better else v > value))
    equal = sum(1 for v in pool if v == value)
    return round((below + equal / 2) / len(pool) * 100, 1)


def normalise(total: float | None, exposure: float, per: float, normalisation: str) -> float | None:
    if total is None:
        return None
    if normalisation != "per_exposure":
        return total
    return total / exposure * per if exposure > 0 else None


@dataclass
class RidgeModel:
    feature_names: list[str]
    mean: np.ndarray
    scale: np.ndarray
    coef: np.ndarray
    intercept: float
    residual_sd: float

    def predict(self, x: np.ndarray) -> np.ndarray:
        return ((x - self.mean) / self.scale) @ self.coef + self.intercept

    def contributions(self, x: np.ndarray) -> np.ndarray:
        """Per-feature effect on the prediction relative to an average player."""
        return ((x - self.mean) / self.scale) * self.coef


def fit_ridge(x: np.ndarray, y: np.ndarray, feature_names: list[str], alpha: float = 1.0) -> RidgeModel:
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    z = (x - mean) / scale
    intercept = float(y.mean())
    coef = np.linalg.solve(z.T @ z + alpha * np.eye(z.shape[1]), z.T @ (y - intercept))
    residuals = y - (z @ coef + intercept)
    dof = max(len(y) - z.shape[1] - 1, 1)
    return RidgeModel(feature_names, mean, scale, coef, intercept, float(math.sqrt((residuals ** 2).sum() / dof)))


def cross_validate(x: np.ndarray, y: np.ndarray, feature_names: list[str], folds: int = 5, z: float = 1.2816) -> dict[str, float]:
    """Mean absolute error (in target units) and coverage of the 80% interval, out of fold."""
    n = len(y)
    order = np.arange(n)
    errors, covered = [], []
    for k in range(folds):
        test = order % folds == k
        if test.sum() == 0 or (~test).sum() <= x.shape[1] + 1:
            continue
        model = fit_ridge(x[~test], y[~test], feature_names)
        predicted = model.predict(x[test])
        errors.extend(np.abs(predicted - y[test]))
        covered.extend(np.abs(predicted - y[test]) <= z * model.residual_sd)
    return {"mae": float(np.mean(errors)) if errors else float("nan"),
            "interval_coverage": float(np.mean(covered)) if covered else float("nan"), "n": n}


def shrink(value: float, exposure: float, prior_mean: float, prior_weight: float) -> tuple[float, float]:
    """Bayesian-style shrinkage toward the role average. Returns (estimate, evidence weight)."""
    weight = exposure / (exposure + prior_weight) if exposure + prior_weight > 0 else 0.0
    return weight * value + (1 - weight) * prior_mean, weight


def next_season_label(label: str) -> str:
    """'2025/26' -> '2026/27', '2025-26' -> '2026-27', '2026' -> '2027'."""
    match = re.fullmatch(r"(\d{4})([/-])(\d{2})", label)
    if match:
        start = int(match.group(1)) + 1
        return f"{start}{match.group(2)}{(start + 1) % 100:02d}"
    if re.fullmatch(r"\d{4}", label):
        return str(int(label) + 1)
    return f"after {label}"


@dataclass
class WorkloadIndicator:
    acute_load: float
    chronic_load: float
    acwr: float | None
    monotony: float | None
    wellness_score: float | None
    flags: list[str]


def workload_indicator(daily_loads: Sequence[float], wellness: Sequence[float]) -> WorkloadIndicator:
    """daily_loads: the last 28 days, oldest first (rest days as 0). wellness: recent daily
    wellness averages on a 1–5 scale (5 = best).

    Acute load is the last 7 days; chronic load is the 28-day weekly average. These are
    monitoring indicators for qualified staff, not injury predictions.
    """
    loads = list(daily_loads)[-28:]
    acute = float(sum(loads[-7:]))
    chronic = float(sum(loads) / 4)
    acwr = round(acute / chronic, 2) if chronic > 0 else None
    week = np.array(loads[-7:], dtype=float)
    monotony = round(float(week.mean() / week.std()), 2) if len(week) and week.std() > 0 else None
    wellness_score = round(float(np.mean(wellness)), 2) if len(wellness) else None
    flags = []
    if acwr is not None and acwr > 1.5:
        flags.append("load_spike")
    if acwr is not None and acwr < 0.8:
        flags.append("underload")
    if monotony is not None and monotony > 2.0:
        flags.append("high_monotony")
    if wellness_score is not None and wellness_score < 2.75:
        flags.append("low_wellness")
    return WorkloadIndicator(round(acute, 1), round(chronic, 1), acwr, monotony, wellness_score, flags)
