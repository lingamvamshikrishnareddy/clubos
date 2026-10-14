import { describe, expect, it } from "vitest";
import { evaluateScenario } from "../src/index.js";

describe("evaluateScenario", () => {
  const budget = { transferBudget: 10_000_000, wageBudget: 30_000_000, currentWageBill: 27_000_000 };

  it("combines signings, sales and renewals", () => {
    const result = evaluateScenario(budget, [
      { playerId: "a", direction: "in", transferFee: 8_000_000, annualSalary: 2_000_000, contractYears: 4 },
      { playerId: "b", direction: "out", transferFee: 3_000_000, currentAnnualSalary: 1_500_000 },
      { playerId: "c", direction: "renew", annualSalary: 1_200_000, currentAnnualSalary: 1_000_000, contractYears: 3 },
    ]);
    expect(result).toEqual({
      feesPaid: 8_000_000,
      feesReceived: 3_000_000,
      netTransferSpend: 5_000_000,
      annualAmortisation: 2_000_000,
      wageChange: 700_000,
      newWageBill: 27_700_000,
      transferBudgetRemaining: 5_000_000,
      wageBudgetRemaining: 2_300_000,
      withinBudget: true,
    });
  });

  it("reports when a scenario breaks the wage budget", () => {
    const result = evaluateScenario(budget, [
      { playerId: "a", direction: "in", transferFee: 0, annualSalary: 4_000_000, contractYears: 2 },
    ]);
    expect(result.wageBudgetRemaining).toBe(-1_000_000);
    expect(result.withinBudget).toBe(false);
  });
});
