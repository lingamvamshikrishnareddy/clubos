import { describe, expect, it } from "vitest";
import { cricket } from "../src/index.js";

describe("Cricket module", () => {
  it("loads a consistent definition", () => {
    expect(cricket.id).toBe("cricket");
    expect(cricket.roles).toHaveLength(9);
    for (const role of cricket.roles) expect(cricket.comparisonMetrics(role.key).length).toBeGreaterThan(0);
  });
});
