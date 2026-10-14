import { describe, expect, it } from "vitest";
import { analyseSquad, defineSport, type SquadPlayer } from "../src/index.js";

const sport = defineSport({
  id: "basketball",
  name: "Test",
  valuationBasis: "annual_salary",
  exposure: { key: "minutes", label: "Minutes", per: 36, minimumForComparison: 300 },
  roles: [
    { key: "guard", label: "Guard", group: "guard" },
    { key: "centre", label: "Centre", group: "big" },
  ],
  eventTypes: [],
  videoTags: [],
  metrics: [{ key: "points", label: "Points", description: "", unit: "points", normalisation: "per_exposure", higherIsBetter: true }],
  comparisonMetrics: { guard: ["points"], centre: ["points"] },
});

const player = (over: Partial<SquadPlayer>): SquadPlayer => ({
  playerId: "p",
  roleKey: "guard",
  age: 25,
  status: "first_team",
  contractEndsOn: "2029-06-30",
  unavailable: false,
  ...over,
});

describe("analyseSquad", () => {
  const result = analyseSquad(
    sport,
    [
      player({ playerId: "g1", age: 33, contractEndsOn: "2027-06-30" }),
      player({ playerId: "g2", age: 32, unavailable: true }),
      player({ playerId: "g3", status: "loaned_out" }),
      player({ playerId: "c1", roleKey: "centre", age: null, contractEndsOn: null }),
      player({ playerId: "c2", roleKey: "centre", status: "academy" }),
    ],
    { asOf: "2026-10-14", minimumByRole: { centre: 2 } },
  );

  it("flags depth that relies on an unavailable player, an ageing group and expiring contracts", () => {
    expect(result[0]).toMatchObject({
      roleKey: "guard",
      senior: 2,
      available: 1,
      ageing: 2,
      expiring: 1,
      issues: ["depth_relies_on_unavailable", "ageing_group", "contracts_expiring"],
    });
  });

  it("excludes academy and loaned-out players and treats unknown age and contract as unknown", () => {
    expect(result[1]).toMatchObject({ roleKey: "centre", senior: 1, ageing: 0, expiring: 0, issues: ["below_minimum_depth"] });
  });
});
