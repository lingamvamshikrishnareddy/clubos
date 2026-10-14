/**
 * The contract every sport implements. Core code (accounts, squads, shortlists,
 * budgets, reporting) depends only on this interface and never on a specific sport.
 * See docs/adr/0001-shared-platform-sport-modules.md.
 */

export type SportId =
  | "soccer"
  | "american_football"
  | "baseball"
  | "basketball"
  | "ice_hockey"
  | "cricket";

/** A tactical role used to compare like with like (e.g. soccer "full_back", baseball "shortstop"). */
export interface Role {
  key: string;
  label: string;
  /** Broad grouping for UI and fallbacks, e.g. "defence", "pitching". */
  group: string;
}

/** An on-field event type in this sport's event model. */
export interface EventType {
  key: string;
  label: string;
}

/**
 * How a raw value is made comparable across players with different playing time.
 * - total: shown as is (e.g. goals saved above expected over a season)
 * - per_exposure: divided by exposure and scaled (e.g. per 90 minutes, per 100 balls)
 * - rate: already a rate or percentage (e.g. strike rate, ERA); never rescaled
 */
export type Normalisation = "total" | "per_exposure" | "rate";

export type MetricUnit =
  | "count"
  | "ratio"
  | "expected_goals"
  | "yards"
  | "mph"
  | "kph"
  | "rpm"
  | "runs"
  | "points";

export interface MetricDefinition {
  key: string;
  label: string;
  description: string;
  unit: MetricUnit;
  normalisation: Normalisation;
  higherIsBetter: boolean;
  /**
   * Typical range of the normalised value for a regular player, used for chart scales
   * and fictional demo data. Not used for any decision.
   */
  typical?: readonly [number, number];
}

export interface ExposureUnit {
  /** e.g. "minutes", "plate_appearances", "balls_faced" */
  key: string;
  label: string;
  /** Per-exposure values are expressed per this many units, e.g. 90 minutes. */
  per: number;
  /** Below this exposure a player's values are flagged as low-sample. */
  minimumForComparison: number;
}

/** A group of video tags, e.g. American football "coverage" = cover 1, cover 2, ... */
export interface TagGroup {
  key: string;
  label: string;
  values: readonly string[];
}

/**
 * A combination of players analysed while on the field together, e.g. a basketball
 * five-man lineup or an ice hockey forward line. Built from player shifts.
 */
export interface UnitDefinition {
  kind: "lineup" | "forward_line" | "defence_pair";
  label: string;
  /** Role groups whose players make up the unit. */
  groups: readonly string[];
  size: number;
  /** Events whose value counts for and against the unit (points, xG). */
  valueEvents: readonly string[];
  valueKind: "points" | "goals" | "xg";
}

/** Formation detection from players' average positions (sports with fixed shapes). */
export interface FormationDefinition {
  /** videoTags group holding the formation vocabulary, e.g. "4-3-3". */
  tagGroup: string;
  outfieldPlayers: number;
  /** Role groups left out of the shape, e.g. goalkeeping. */
  excludeGroups: readonly string[];
}

/**
 * What a player's market value means in this sport: a transfer fee (soccer) or the annual
 * salary the market pays (leagues with drafts, trades, free agency or auctions).
 */
export type ValuationBasis = "transfer_fee" | "annual_salary";

export interface SportModule {
  id: SportId;
  name: string;
  valuationBasis: ValuationBasis;
  /** Exposure unit for roles that don't override it. */
  exposure: ExposureUnit;
  /** Roles measured differently, e.g. pitchers by batters faced rather than plate appearances. */
  roleExposure?: Readonly<Record<string, ExposureUnit>>;
  roles: readonly Role[];
  eventTypes: readonly EventType[];
  metrics: readonly MetricDefinition[];
  units?: readonly UnitDefinition[];
  formation?: FormationDefinition;
  /** Vocabulary for tagging video in this sport (Stage 2). */
  videoTags: readonly TagGroup[];
  /** Metrics shown by default when comparing players in a role. */
  comparisonMetrics(roleKey: string): readonly string[];
}

export function exposureFor(sport: SportModule, roleKey: string): ExposureUnit {
  return sport.roleExposure?.[roleKey] ?? sport.exposure;
}
