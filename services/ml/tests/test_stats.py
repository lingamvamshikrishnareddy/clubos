import numpy as np
import pytest

from clubos_ml.stats import (
    cross_validate,
    fit_ridge,
    next_season_label,
    normalise,
    percentile_rank,
    shrink,
    workload_indicator,
)


def test_percentile_rank_matches_core_rule():
    assert percentile_rank(3, [1, 2, 3, 4], True) == 62.5
    assert percentile_rank(1, [1, 2, 3, 4], False) == 87.5
    assert percentile_rank(1, [], True) is None


def test_normalise_keeps_missing_missing():
    assert normalise(None, 900, 90, "per_exposure") is None
    assert normalise(10, 900, 90, "per_exposure") == 1
    assert normalise(0.31, 900, 90, "rate") == 0.31
    assert normalise(3, 0, 90, "per_exposure") is None


def test_ridge_recovers_signal_and_interval_is_calibrated():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(600, 3))
    y = 2.0 * x[:, 0] - 1.0 * x[:, 1] + rng.normal(scale=0.5, size=600)
    model = fit_ridge(x, y, ["a", "b", "c"], alpha=0.1)
    assert model.coef == pytest.approx([2.0, -1.0, 0.0], abs=0.1)
    assert model.residual_sd == pytest.approx(0.5, abs=0.05)
    validation = cross_validate(x, y, ["a", "b", "c"])
    assert validation["interval_coverage"] == pytest.approx(0.8, abs=0.05)


def test_shrinkage_weights_by_exposure():
    assert shrink(10, 0, 4, 100) == (4, 0)
    estimate, weight = shrink(10, 300, 4, 100)
    assert weight == 0.75
    assert estimate == pytest.approx(8.5)


@pytest.mark.parametrize("label, expected", [("2025/26", "2026/27"), ("2025-26", "2026-27"), ("2026", "2027"), ("Spring", "after Spring")])
def test_next_season_label(label, expected):
    assert next_season_label(label) == expected


def test_workload_indicator_flags_a_spike():
    steady = [300.0, 400, 0, 350, 300, 450, 0] * 3
    spike = [600.0, 700, 0, 650, 600, 750, 0]
    ind = workload_indicator(steady + spike, [2.4, 2.6, 2.8])
    # acute 3,300 / chronic (3 x 1,800 + 3,300) / 4 = 2,175
    assert ind.acwr == pytest.approx(1.52, abs=0.01)
    assert "load_spike" in ind.flags
    assert "low_wellness" in ind.flags


def test_workload_indicator_without_history_has_no_ratio():
    ind = workload_indicator([0.0] * 28, [])
    assert ind.acwr is None and ind.monotony is None and ind.flags == []


def test_time_slices_split_overlapping_shifts():
    from clubos_ml.analytics import time_slices

    slices = time_slices([("a", 0, 60), ("b", 0, 30), ("c", 30, 60)])
    assert slices == [(0, 30, frozenset({"a", "b"})), (30, 60, frozenset({"a", "c"}))]


def test_detect_lines_picks_the_formation_with_the_tightest_lines():
    from clubos_ml.analytics import detect_lines

    xs = [22, 23, 31, 33, 40, 51, 65, 71, 73, 84]  # back four, two holding, three behind one striker
    formation, confidence = detect_lines(xs, ["4-3-3", "4-2-3-1", "4-4-2", "3-5-2"])
    assert formation == "4-2-3-1"
    assert confidence > 0.9
    assert detect_lines([10, 20], ["4-3-3"]) == ("unknown", 0.0)


def test_traded_player_rows_are_merged():
    from datetime import date

    from clubos_ml.pipeline import Sample, merge_team_rows

    metrics = {"rushing_yards": {"normalisation": "per_exposure"}, "yards_per_carry": {"normalisation": "rate"},
               "pass_attempts": {"normalisation": "per_exposure"},
               "completion_pct": {"normalisation": "rate", "weightBy": "pass_attempts"}}
    rows = [
        Sample("p", "c", "s", "2024", "running_back", 300, date(1997, 1, 1), {"rushing_yards": 400, "yards_per_carry": 4.0},
               exposure_unit="snaps"),
        Sample("p", "c", "s", "2024", "wide_receiver", 100, date(1997, 1, 1), {"rushing_yards": 100, "yards_per_carry": 5.0},
               exposure_unit="snaps"),
        Sample("q", "c", "s", "2024", "running_back", 50, None, {"rushing_yards": None}, exposure_unit="snaps"),
        # Traded quarterback: completion % combines by attempts, not snaps (213 / 310).
        Sample("qb", "c", "s", "2024", "quarterback", 400, None, {"pass_attempts": 300, "completion_pct": 0.70}, exposure_unit="snaps"),
        Sample("qb", "c", "s", "2024", "quarterback", 100, None, {"pass_attempts": 10, "completion_pct": 0.30}, exposure_unit="snaps"),
        # Rows in a different unit are not added to the main row.
        Sample("k", "c", "s", "2024", "kicker", 30, None, {}, exposure_unit="kicks"),
        Sample("k", "c", "s", "2024", "punter", 5, None, {}, exposure_unit="punts"),
    ]
    merged = {s.player_id: s for s in merge_team_rows(rows, metrics)}
    assert merged["p"].role == "running_back" and merged["p"].exposure == 400
    assert merged["p"].totals == {"rushing_yards": 500, "yards_per_carry": 4.25}
    assert merged["q"].totals == {"rushing_yards": None}
    assert merged["qb"].totals["completion_pct"] == pytest.approx(213 / 310)
    assert merged["k"].exposure == 30 and merged["k"].exposure_unit == "kicks"
