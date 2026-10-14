import { describe, expect, it } from "vitest";
import { baseball } from "../src/index.js";

describe("Baseball module", () => {
  it("loads a consistent definition", () => {
    expect(baseball.id).toBe("baseball");
    expect(baseball.roles).toHaveLength(11);
    for (const role of baseball.roles) expect(baseball.comparisonMetrics(role.key).length).toBeGreaterThan(0);
  });
});
