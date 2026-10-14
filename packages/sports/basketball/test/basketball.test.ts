import { describe, expect, it } from "vitest";
import { basketball } from "../src/index.js";

describe("Basketball module", () => {
  it("loads a consistent definition", () => {
    expect(basketball.id).toBe("basketball");
    expect(basketball.roles).toHaveLength(5);
    for (const role of basketball.roles) expect(basketball.comparisonMetrics(role.key).length).toBeGreaterThan(0);
  });
});
