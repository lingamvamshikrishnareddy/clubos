import type { MetricDefinition, Role, SportModule } from "@clubos/core";
import metricsJson from "../metrics.json";
import rolesJson from "../roles.json";

// metrics.json and roles.json are shared with the Python services so both sides agree on keys.
const metrics = metricsJson as MetricDefinition[];

const roles = rolesJson as Role[];

export type SoccerRoleKey =
  | "goalkeeper"
  | "centre_back"
  | "full_back"
  | "defensive_midfielder"
  | "central_midfielder"
  | "attacking_midfielder"
  | "winger"
  | "striker";

const comparisonMetricsByRole: Record<SoccerRoleKey, readonly string[]> = {
  // Goalkeeping needs shot-stopping metrics (post-shot xG) that the open-data connector
  // does not produce yet; distribution is the comparable part for now.
  goalkeeper: ["passes_attempted", "passes_completed", "progressive_passes"],
  centre_back: ["tackles_won", "interceptions", "ball_recoveries", "progressive_passes", "passes_completed"],
  full_back: ["progressive_passes", "progressive_carries", "key_passes", "tackles_won", "interceptions"],
  defensive_midfielder: ["ball_recoveries", "interceptions", "tackles_won", "pressures", "progressive_passes"],
  central_midfielder: ["progressive_passes", "progressive_carries", "key_passes", "pressures", "ball_recoveries"],
  attacking_midfielder: ["xa", "key_passes", "np_xg", "dribbles_completed", "progressive_carries"],
  winger: ["np_xg", "xa", "dribbles_completed", "progressive_carries", "key_passes"],
  striker: ["np_xg", "goals", "shots", "xa", "pressures"],
};

export const soccer: SportModule = {
  id: "soccer",
  name: "Association football",
  exposure: { key: "minutes", per: 90, minimumForComparison: 450 },
  roles,
  eventTypes: [
    { key: "pass", label: "Pass" },
    { key: "carry", label: "Carry" },
    { key: "dribble", label: "Dribble" },
    { key: "shot", label: "Shot" },
    { key: "pressure", label: "Pressure" },
    { key: "duel", label: "Duel" },
    { key: "interception", label: "Interception" },
    { key: "ball_recovery", label: "Ball recovery" },
    { key: "clearance", label: "Clearance" },
    { key: "block", label: "Block" },
    { key: "foul_committed", label: "Foul committed" },
    { key: "substitution", label: "Substitution" },
  ],
  metrics,
  comparisonMetrics: (roleKey) => comparisonMetricsByRole[roleKey as SoccerRoleKey] ?? [],
};
