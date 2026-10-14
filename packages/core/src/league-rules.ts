/**
 * League rules (from packages/leagues/leagues.json, stored in competitions.rules) and
 * checks of a roster or a planned roster against them: salary caps, auction purses,
 * squad sizes and overseas-player limits. Sport-agnostic: the rules say what applies.
 */

export interface LeagueRules {
  /** The season these values apply to; rules change every year. */
  season: string;
  salaryCap?: {
    kind: "hard" | "soft";
    amount: number;
    currency: string;
    luxuryTaxLine?: number;
    firstApron?: number;
    secondApron?: number;
  };
  auctionPurse?: { amount: number; currency: string };
  squadSize?: { min?: number; max: number; label?: string };
  foreignPlayers?: { homeNationality: string; maxInSquad?: number; maxInLineup?: number; label?: string };
}

export interface RosterPlayer {
  playerId: string;
  annualSalary: number;
  /** Null when unknown; such players cannot be checked against nationality limits. */
  nationality: string | null;
}

export type RuleSeverity = "breach" | "warning" | "info";

export interface RuleFinding {
  rule: "salary_cap" | "luxury_tax" | "first_apron" | "second_apron" | "auction_purse" | "squad_size" | "foreign_players";
  severity: RuleSeverity;
  message: string;
  value: number;
  limit: number;
}

export interface RosterCheck {
  payroll: number;
  squadSize: number;
  foreignPlayers: number;
  unknownNationality: number;
  findings: RuleFinding[];
}

function money(amount: number, currency: string): string {
  return `${currency} ${Math.round(amount).toLocaleString("en-US")}`;
}

export function checkRoster(rules: LeagueRules, roster: readonly RosterPlayer[]): RosterCheck {
  const payroll = roster.reduce((sum, p) => sum + p.annualSalary, 0);
  const home = rules.foreignPlayers?.homeNationality;
  const foreign = home ? roster.filter((p) => p.nationality !== null && p.nationality !== home).length : 0;
  const unknown = home ? roster.filter((p) => p.nationality === null).length : 0;
  const findings: RuleFinding[] = [];

  const cap = rules.salaryCap;
  if (cap) {
    if (payroll > cap.amount) {
      findings.push({
        rule: "salary_cap",
        severity: cap.kind === "hard" ? "breach" : "warning",
        message:
          cap.kind === "hard"
            ? `Payroll ${money(payroll, cap.currency)} is over the hard cap of ${money(cap.amount, cap.currency)}.`
            : `Payroll is over the soft cap of ${money(cap.amount, cap.currency)}: signings need cap exceptions.`,
        value: payroll,
        limit: cap.amount,
      });
    }
    const tiers: [RuleFinding["rule"], number | undefined, string][] = [
      ["luxury_tax", cap.luxuryTaxLine, "Over the luxury tax line: tax is owed on the excess."],
      ["first_apron", cap.firstApron, "Over the first apron: some transaction tools are restricted."],
      ["second_apron", cap.secondApron, "Over the second apron: further restrictions apply."],
    ];
    for (const [rule, limit, message] of tiers) {
      if (limit !== undefined && payroll > limit) {
        findings.push({ rule, severity: rule === "second_apron" ? "breach" : "warning", message, value: payroll, limit });
      }
    }
  }

  const purse = rules.auctionPurse;
  if (purse && payroll > purse.amount) {
    findings.push({
      rule: "auction_purse",
      severity: "breach",
      message: `Squad spend ${money(payroll, purse.currency)} exceeds the auction purse of ${money(purse.amount, purse.currency)}.`,
      value: payroll,
      limit: purse.amount,
    });
  }

  const size = rules.squadSize;
  if (size && roster.length > size.max) {
    findings.push({
      rule: "squad_size",
      severity: "breach",
      message: `${roster.length} players is above the maximum of ${size.max}${size.label ? ` (${size.label})` : ""}.`,
      value: roster.length,
      limit: size.max,
    });
  }
  if (size?.min !== undefined && roster.length < size.min) {
    findings.push({
      rule: "squad_size",
      severity: "breach",
      message: `${roster.length} players is below the minimum of ${size.min}.`,
      value: roster.length,
      limit: size.min,
    });
  }

  const fp = rules.foreignPlayers;
  if (fp?.maxInSquad !== undefined) {
    const label = fp.label ?? "foreign players";
    if (foreign > fp.maxInSquad) {
      findings.push({
        rule: "foreign_players",
        severity: "breach",
        message: `${foreign} ${label} is above the limit of ${fp.maxInSquad}.`,
        value: foreign,
        limit: fp.maxInSquad,
      });
    } else if (unknown > 0 && foreign + unknown > fp.maxInSquad) {
      findings.push({
        rule: "foreign_players",
        severity: "info",
        message: `${unknown} player(s) have no recorded nationality, so the ${label} limit cannot be confirmed.`,
        value: foreign + unknown,
        limit: fp.maxInSquad,
      });
    }
  }

  return { payroll, squadSize: roster.length, foreignPlayers: foreign, unknownNationality: unknown, findings };
}

export type RosterMove =
  | { direction: "in"; player: RosterPlayer }
  | { direction: "out"; playerId: string }
  | { direction: "renew"; playerId: string; annualSalary: number };

/** Applies planned signings, departures and renewals, then checks the result. */
export function checkPlannedRoster(
  rules: LeagueRules,
  roster: readonly RosterPlayer[],
  moves: readonly RosterMove[],
): RosterCheck {
  let planned = [...roster];
  for (const move of moves) {
    if (move.direction === "in") planned.push(move.player);
    else if (move.direction === "out") planned = planned.filter((p) => p.playerId !== move.playerId);
    else planned = planned.map((p) => (p.playerId === move.playerId ? { ...p, annualSalary: move.annualSalary } : p));
  }
  return checkRoster(rules, planned);
}
