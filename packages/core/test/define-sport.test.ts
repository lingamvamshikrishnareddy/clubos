import { describe, expect, it } from "vitest";
import { defineSport, exposureFor, type SportDefinition } from "../src/index.js";

const valid: SportDefinition = {
  id: "cricket",
  name: "Test",
  valuationBasis: "annual_salary",
  exposure: { key: "balls_faced", label: "Balls faced", per: 100, minimumForComparison: 300 },
  roleExposure: { bowler: { key: "balls_bowled", label: "Balls bowled", per: 120, minimumForComparison: 360 } },
  roles: [
    { key: "batter", label: "Batter", group: "batting" },
    { key: "bowler", label: "Bowler", group: "bowling" },
  ],
  eventTypes: [],
  videoTags: [],
  metrics: [
    { key: "runs", label: "Runs", description: "", unit: "runs", normalisation: "per_exposure", higherIsBetter: true, typical: [80, 170] },
    { key: "wickets", label: "Wickets", description: "", unit: "count", normalisation: "per_exposure", higherIsBetter: true },
  ],
  comparisonMetrics: { batter: ["runs"], bowler: ["wickets"] },
};

describe("defineSport", () => {
  it("builds a module with role-specific exposure", () => {
    const sport = defineSport(valid);
    expect(sport.comparisonMetrics("bowler")).toEqual(["wickets"]);
    expect(exposureFor(sport, "bowler").key).toBe("balls_bowled");
    expect(exposureFor(sport, "batter").key).toBe("balls_faced");
  });

  it.each([
    ["unknown metric", { ...valid, comparisonMetrics: { batter: ["runs"], bowler: ["sixes"] } }, /unknown metric sixes/],
    ["role without metrics", { ...valid, comparisonMetrics: { batter: ["runs"] } }, /bowler has no comparison metrics/],
    ["exposure for unknown role", { ...valid, roleExposure: { keeper: valid.exposure } }, /exposure for unknown role keeper/],
    [
      "inverted typical range",
      { ...valid, metrics: [{ ...valid.metrics[0]!, typical: [170, 80] as const }, valid.metrics[1]!] },
      /typical must be/,
    ],
    [
      "unit with an unknown role group",
      { ...valid, units: [{ kind: "lineup", label: "L", groups: ["fielding"], size: 2, valueEvents: [], valueKind: "points" }] },
      /unknown role group fielding/,
    ],
  ])("rejects %s", (_, definition, message) => {
    expect(() => defineSport(definition as SportDefinition)).toThrow(message);
  });
});
