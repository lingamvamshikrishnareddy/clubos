import { describe, expect, it } from "vitest";
import { compareInRole, normalise, percentileRank, type SportModule } from "../src/index.js";

const sport: SportModule = {
  id: "soccer",
  name: "Test sport",
  valuationBasis: "transfer_fee",
  exposure: { key: "minutes", label: "Minutes", per: 90, minimumForComparison: 450 },
  roleExposure: { keeper: { key: "shots_faced", label: "Shots faced", per: 10, minimumForComparison: 50 } },
  videoTags: [],
  roles: [
    { key: "striker", label: "Striker", group: "attack" },
    { key: "keeper", label: "Keeper", group: "keeping" },
  ],
  eventTypes: [],
  metrics: [
    { key: "goals", label: "Goals", description: "", unit: "count", normalisation: "per_exposure", higherIsBetter: true },
    { key: "turnovers", label: "Turnovers", description: "", unit: "count", normalisation: "per_exposure", higherIsBetter: false },
  ],
  comparisonMetrics: () => ["goals", "turnovers", "not_a_metric"],
};

describe("normalise", () => {
  const goals = sport.metrics[0]!;
  it("scales per exposure", () => expect(normalise(goals, 10, 900, 90)).toBe(1));
  it("keeps missing data missing", () => expect(normalise(goals, null, 900, 90)).toBeNull());
  it("returns null without exposure", () => expect(normalise(goals, 3, 0, 90)).toBeNull());
});

describe("percentileRank", () => {
  it("ranks higher-is-better", () => expect(percentileRank(3, [1, 2, 3, 4], true)).toBe(63));
  it("ranks lower-is-better", () => expect(percentileRank(1, [1, 2, 3, 4], false)).toBe(88));
  it("returns null for an empty pool", () => expect(percentileRank(1, [], true)).toBeNull());
});

describe("compareInRole", () => {
  const result = compareInRole(sport, "striker", [
    { playerId: "a", roleKey: "striker", exposure: 900, totals: { goals: 10, turnovers: 20 } },
    { playerId: "b", roleKey: "striker", exposure: 900, totals: { goals: 5, turnovers: null } },
    { playerId: "c", roleKey: "striker", exposure: 90, totals: { goals: 3, turnovers: 0 } },
    { playerId: "d", roleKey: "winger", exposure: 900, totals: { goals: 50, turnovers: 0 } },
  ]);

  it("only includes players in the role and ignores unknown metric keys", () => {
    expect(result.map((r) => r.playerId)).toEqual(["a", "b", "c"]);
    expect(result[0]!.metrics.map((m) => m.metricKey)).toEqual(["goals", "turnovers"]);
  });

  it("excludes low-sample players from the pool but still flags and scores them", () => {
    const c = result[2]!;
    expect(c.lowSample).toBe(true);
    expect(c.metrics[0]).toEqual({ metricKey: "goals", value: 3, percentile: 100, poolSize: 2 });
  });

  it("does not treat missing values as zero", () => {
    const b = result[1]!;
    expect(b.metrics[1]).toEqual({ metricKey: "turnovers", value: null, percentile: null, poolSize: 1 });
  });
});

describe("role-specific exposure", () => {
  it("uses the role's own exposure unit for scaling and the low-sample threshold", () => {
    const [keeper] = compareInRole(sport, "keeper", [
      { playerId: "k", roleKey: "keeper", exposure: 60, totals: { goals: 3, turnovers: 0 } },
    ]);
    expect(keeper!.lowSample).toBe(false);
    expect(keeper!.metrics[0]!.value).toBe(0.5);
  });
});
