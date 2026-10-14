import type {
  EventType,
  ExposureUnit,
  MetricDefinition,
  Role,
  SportId,
  SportModule,
  TagGroup,
  UnitDefinition,
  FormationDefinition,
  ValuationBasis,
} from "./sport-module.js";

/**
 * The JSON shape of packages/sports/<sport>/sport.json. Keeping sport definitions as
 * data lets the TypeScript app and the Python services share them (ADR-0001).
 */
export interface SportDefinition {
  id: SportId;
  name: string;
  valuationBasis: ValuationBasis;
  exposure: ExposureUnit;
  roleExposure?: Record<string, ExposureUnit>;
  roles: Role[];
  eventTypes: EventType[];
  videoTags: TagGroup[];
  metrics: MetricDefinition[];
  units?: UnitDefinition[];
  formation?: FormationDefinition;
  comparisonMetrics: Record<string, string[]>;
}

/** Builds a SportModule and checks the definition is internally consistent. */
export function defineSport(definition: SportDefinition): SportModule {
  const metricKeys = new Set(definition.metrics.map((m) => m.key));
  const roleKeys = new Set(definition.roles.map((r) => r.key));
  const problems: string[] = [];
  if (metricKeys.size !== definition.metrics.length) problems.push("duplicate metric keys");
  if (roleKeys.size !== definition.roles.length) problems.push("duplicate role keys");
  for (const metric of definition.metrics) {
    const t = metric.typical;
    if (t && (t.length !== 2 || t[0] > t[1])) problems.push(`metric ${metric.key}: typical must be [low, high]`);
  }
  for (const role of roleKeys) {
    const keys = definition.comparisonMetrics[role];
    if (!keys?.length) problems.push(`role ${role} has no comparison metrics`);
    for (const key of keys ?? []) if (!metricKeys.has(key)) problems.push(`role ${role}: unknown metric ${key}`);
  }
  for (const role of Object.keys(definition.comparisonMetrics)) {
    if (!roleKeys.has(role)) problems.push(`comparison metrics for unknown role ${role}`);
  }
  for (const role of Object.keys(definition.roleExposure ?? {})) {
    if (!roleKeys.has(role)) problems.push(`exposure for unknown role ${role}`);
  }
  const groups = new Set(definition.roles.map((r) => r.group));
  const eventKeys = new Set(definition.eventTypes.map((e) => e.key));
  const tagGroups = new Set(definition.videoTags.map((t) => t.key));
  for (const unit of definition.units ?? []) {
    for (const g of unit.groups) if (!groups.has(g)) problems.push(`unit ${unit.kind}: unknown role group ${g}`);
    for (const e of unit.valueEvents) if (!eventKeys.has(e)) problems.push(`unit ${unit.kind}: unknown event ${e}`);
  }
  if (definition.formation) {
    if (!tagGroups.has(definition.formation.tagGroup)) problems.push(`formation: unknown tag group ${definition.formation.tagGroup}`);
    for (const g of definition.formation.excludeGroups) if (!groups.has(g)) problems.push(`formation: unknown role group ${g}`);
  }
  if (problems.length) throw new Error(`Invalid sport definition ${definition.id}: ${problems.join("; ")}`);

  const { comparisonMetrics, roleExposure, ...rest } = definition;
  return {
    ...rest,
    ...(roleExposure ? { roleExposure } : {}),
    comparisonMetrics: (roleKey) => comparisonMetrics[roleKey] ?? [],
  };
}
