import { describe, expect, it } from "vitest";
import { soccer } from "../src/index.js";

describe("soccer module", () => {
  it("exposes eight roles measured in minutes per 90", () => {
    expect(soccer.roles).toHaveLength(8);
    expect(soccer.exposure).toMatchObject({ key: "minutes", per: 90 });
  });

  it("returns no comparison metrics for an unknown role", () => {
    expect(soccer.comparisonMetrics("point_guard")).toEqual([]);
  });
});
