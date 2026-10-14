/**
 * Recruitment budget scenarios: what a set of signings, sales and renewals does to the
 * transfer budget, the wage bill and the annual cost including fee amortisation.
 * Currency-agnostic: all amounts must be in the scenario's currency.
 */

export type ScenarioMove =
  | { playerId: string; direction: "in"; transferFee: number; annualSalary: number; contractYears: number }
  | { playerId: string; direction: "out"; transferFee: number; currentAnnualSalary: number }
  | { playerId: string; direction: "renew"; annualSalary: number; currentAnnualSalary: number; contractYears: number };

export interface ScenarioBudget {
  transferBudget: number;
  wageBudget: number;
  currentWageBill: number;
}

export interface ScenarioResult {
  feesPaid: number;
  feesReceived: number;
  netTransferSpend: number;
  /** Fees paid spread over contract length: the annual cost a signing adds to the accounts. */
  annualAmortisation: number;
  wageChange: number;
  newWageBill: number;
  transferBudgetRemaining: number;
  wageBudgetRemaining: number;
  withinBudget: boolean;
}

export function evaluateScenario(budget: ScenarioBudget, moves: readonly ScenarioMove[]): ScenarioResult {
  let feesPaid = 0;
  let feesReceived = 0;
  let annualAmortisation = 0;
  let wageChange = 0;

  for (const move of moves) {
    switch (move.direction) {
      case "in":
        feesPaid += move.transferFee;
        annualAmortisation += move.transferFee / Math.max(move.contractYears, 1);
        wageChange += move.annualSalary;
        break;
      case "out":
        feesReceived += move.transferFee;
        wageChange -= move.currentAnnualSalary;
        break;
      case "renew":
        wageChange += move.annualSalary - move.currentAnnualSalary;
        break;
    }
  }

  const netTransferSpend = feesPaid - feesReceived;
  const newWageBill = budget.currentWageBill + wageChange;
  const transferBudgetRemaining = budget.transferBudget - netTransferSpend;
  const wageBudgetRemaining = budget.wageBudget - newWageBill;
  return {
    feesPaid,
    feesReceived,
    netTransferSpend,
    annualAmortisation: Math.round(annualAmortisation * 100) / 100,
    wageChange,
    newWageBill,
    transferBudgetRemaining,
    wageBudgetRemaining,
    withinBudget: transferBudgetRemaining >= 0 && wageBudgetRemaining >= 0,
  };
}
