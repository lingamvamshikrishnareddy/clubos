import { describe, expect, it } from "vitest";
import { soccer } from "../src/index.js";

describe("soccer module", () => {
  const metricKeys = new Set(soccer.metrics.map((m) => m.key));

  it("has unique metric and role keys", () => {
    expect(metricKeys.size).toBe(soccer.metrics.length);
    expect(new Set(soccer.roles.map((r) => r.key)).size).toBe(soccer.roles.length);
  });

  it("defines comparison metrics for every role, using only known metrics", () => {
    for (const role of soccer.roles) {
      const keys = soccer.comparisonMetrics(role.key);
      expect(keys.length, role.key).toBeGreaterThan(0);
      for (const key of keys) expect(metricKeys.has(key), `${role.key}: ${key}`).toBe(true);
    }
  });

  it("returns no comparison metrics for an unknown role", () => {
    expect(soccer.comparisonMetrics("point_guard")).toEqual([]);
  });
});
