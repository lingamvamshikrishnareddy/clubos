import { describe, expect, it } from "vitest";
import { iceHockey } from "../src/index.js";

describe("Ice hockey module", () => {
  it("loads a consistent definition", () => {
    expect(iceHockey.id).toBe("ice_hockey");
    expect(iceHockey.roles).toHaveLength(4);
    for (const role of iceHockey.roles) expect(iceHockey.comparisonMetrics(role.key).length).toBeGreaterThan(0);
  });
});
