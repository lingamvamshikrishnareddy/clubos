import { describe, expect, it } from "vitest";
import leagues from "../../leagues/leagues.json";
import { checkPlannedRoster, checkRoster, type LeagueRules, type RosterPlayer } from "../src/index.js";

const rulesFor = (key: string) => leagues.leagues.find((l) => l.key === key)!.rules as unknown as LeagueRules;

const roster = (count: number, salary: number, nationality: string | null = "India"): RosterPlayer[] =>
  Array.from({ length: count }, (_, i) => ({ playerId: `p${i}`, annualSalary: salary, nationality }));

describe("league rules from the reference file", () => {
  it("NFL: a hard cap is a breach", () => {
    const result = checkRoster(rulesFor("nfl"), roster(53, 5_400_000, null));
    expect(result.payroll).toBe(286_200_000);
    expect(result.findings.map((f) => [f.rule, f.severity])).toEqual([["salary_cap", "breach"]]);
  });

  it("NBA: soft cap, tax line and aprons are tiers", () => {
    const result = checkRoster(rulesFor("nba"), roster(15, 13_200_000, null));  // 198M: over cap, tax and first apron
    expect(result.findings.map((f) => [f.rule, f.severity])).toEqual([
      ["salary_cap", "warning"],
      ["luxury_tax", "warning"],
      ["first_apron", "warning"],
    ]);
  });

  it("IPL: overseas limit, purse and squad size", () => {
    // 16 x 3 crore + 9 overseas x 8.5 crore = 124.5 crore: over the 120 crore purse and the overseas limit.
    const squad = [...roster(16, 30_000_000), ...roster(9, 85_000_000, "Australia")].map((p, i) => ({ ...p, playerId: `p${i}` }));
    const result = checkRoster(rulesFor("ipl"), squad);
    expect(result.foreignPlayers).toBe(9);
    expect(result.findings.map((f) => f.rule).sort()).toEqual(["auction_purse", "foreign_players"]);

    const fixed = checkPlannedRoster(rulesFor("ipl"), squad, [
      { direction: "out", playerId: "p24" },
      { direction: "renew", playerId: "p23", annualSalary: 20_000_000 },
    ]);
    expect(fixed.findings).toEqual([]);
  });

  it("reports unknown nationalities instead of assuming", () => {
    const squad = [...roster(10, 1_000_000), ...roster(8, 1_000_000, "England"), ...roster(2, 1_000_000, null)].map((p, i) => ({
      ...p,
      playerId: `p${i}`,
    }));
    const result = checkRoster(rulesFor("ipl"), squad);
    expect(result.findings).toEqual([expect.objectContaining({ rule: "foreign_players", severity: "info" })]);
  });

  it("football leagues have no cap rules, so nothing is flagged", () => {
    expect(checkRoster(rulesFor("efl_championship"), roster(30, 2_000_000, null)).findings).toEqual([]);
  });
});
