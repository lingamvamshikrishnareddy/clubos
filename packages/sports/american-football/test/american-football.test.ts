import { describe, expect, it } from "vitest";
import { americanFootball } from "../src/index.js";

describe("American football module", () => {
  it("loads a consistent definition", () => {
    expect(americanFootball.id).toBe("american_football");
    expect(americanFootball.roles).toHaveLength(12);
    for (const role of americanFootball.roles) expect(americanFootball.comparisonMetrics(role.key).length).toBeGreaterThan(0);
  });
});
