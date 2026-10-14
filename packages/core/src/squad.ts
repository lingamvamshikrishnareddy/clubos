import type { SportModule } from "./sport-module.js";

export type SquadStatus = "first_team" | "reserve" | "academy" | "loaned_out";

export interface SquadPlayer {
  playerId: string;
  roleKey: string | null;
  /** Null when the birth date is unknown. */
  age: number | null;
  status: SquadStatus;
  /** ISO date; null when no contract is recorded. */
  contractEndsOn: string | null;
  unavailable: boolean;
}

export type RoleIssue =
  | "below_minimum_depth"
  | "depth_relies_on_unavailable"
  | "ageing_group"
  | "contracts_expiring";

export interface RoleDepth {
  roleKey: string;
  label: string;
  minimum: number;
  /** First-team and reserve players in the role (loaned-out and academy excluded). */
  senior: number;
  available: number;
  ageing: number;
  expiring: number;
  issues: RoleIssue[];
}

export interface SquadAnalysisOptions {
  /** ISO date the analysis is for. */
  asOf: string;
  /** Minimum senior players wanted per role; roles not listed use `defaultMinimum`. */
  minimumByRole?: Readonly<Record<string, number>>;
  defaultMinimum?: number;
  ageingFrom?: number;
  expiringWithinMonths?: number;
}

function addMonths(isoDate: string, months: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + months);
  return d.toISOString().slice(0, 10);
}

/** Depth per role with the issues a sporting director should look at, in role order. */
export function analyseSquad(
  sport: SportModule,
  players: readonly SquadPlayer[],
  options: SquadAnalysisOptions,
): RoleDepth[] {
  const { asOf, minimumByRole = {}, defaultMinimum = 2, ageingFrom = 31, expiringWithinMonths = 12 } = options;
  const expiryCutoff = addMonths(asOf, expiringWithinMonths);

  return sport.roles.map((role) => {
    const senior = players.filter(
      (p) => p.roleKey === role.key && (p.status === "first_team" || p.status === "reserve"),
    );
    const minimum = minimumByRole[role.key] ?? defaultMinimum;
    const available = senior.filter((p) => !p.unavailable).length;
    const ageing = senior.filter((p) => p.age !== null && p.age >= ageingFrom).length;
    const expiring = senior.filter((p) => p.contractEndsOn !== null && p.contractEndsOn <= expiryCutoff).length;

    const issues: RoleIssue[] = [];
    if (senior.length < minimum) issues.push("below_minimum_depth");
    else if (available < minimum) issues.push("depth_relies_on_unavailable");
    if (senior.length > 0 && ageing * 2 >= senior.length) issues.push("ageing_group");
    if (expiring > 0) issues.push("contracts_expiring");

    return { roleKey: role.key, label: role.label, minimum, senior: senior.length, available, ageing, expiring, issues };
  });
}
