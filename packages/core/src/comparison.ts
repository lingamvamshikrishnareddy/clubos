import type { MetricDefinition, SportModule } from "./sport-module.js";

/**
 * A player's aggregated output over some period, as stored by ingestion.
 * `null` means the source did not measure the metric. It is never treated as zero.
 */
export interface PlayerSample {
  playerId: string;
  roleKey: string;
  exposure: number;
  totals: Readonly<Record<string, number | null>>;
}

export interface MetricComparison {
  metricKey: string;
  value: number | null;
  /** 0–100, where 100 is best in the pool (direction-aware). Null when not comparable. */
  percentile: number | null;
  poolSize: number;
}

export interface PlayerComparison {
  playerId: string;
  lowSample: boolean;
  metrics: MetricComparison[];
}

/** Turns a total into a comparable value according to the metric's normalisation. */
export function normalise(
  metric: MetricDefinition,
  total: number | null | undefined,
  exposure: number,
  per: number,
): number | null {
  if (total === null || total === undefined) return null;
  if (metric.normalisation !== "per_exposure") return total;
  if (exposure <= 0) return null;
  return (total / exposure) * per;
}

/**
 * Direction-aware percentile rank of `value` among `pool` (mid-rank for ties).
 * Returns null when there is nothing to compare against.
 */
export function percentileRank(
  value: number,
  pool: readonly number[],
  higherIsBetter: boolean,
): number | null {
  if (pool.length === 0) return null;
  let below = 0;
  let equal = 0;
  for (const other of pool) {
    if (other === value) equal++;
    else if (higherIsBetter ? other < value : other > value) below++;
  }
  return Math.round(((below + equal / 2) / pool.length) * 100);
}

/**
 * Compares players in the same role on the sport's comparison metrics.
 * Only players with enough exposure form the reference pool, so a striker who played
 * 30 minutes cannot top the league on per-90 numbers. Low-sample players are still
 * returned, flagged, so scouts can see them.
 */
export function compareInRole(
  sport: SportModule,
  roleKey: string,
  samples: readonly PlayerSample[],
): PlayerComparison[] {
  const metricsByKey = new Map(sport.metrics.map((m) => [m.key, m]));
  const metricKeys = sport.comparisonMetrics(roleKey).filter((k) => metricsByKey.has(k));
  const inRole = samples.filter((s) => s.roleKey === roleKey);
  const { per, minimumForComparison } = sport.exposure;

  const valueOf = (s: PlayerSample, metric: MetricDefinition) =>
    normalise(metric, s.totals[metric.key], s.exposure, per);

  const pools = new Map<string, number[]>();
  for (const key of metricKeys) {
    const metric = metricsByKey.get(key)!;
    pools.set(
      key,
      inRole
        .filter((s) => s.exposure >= minimumForComparison)
        .map((s) => valueOf(s, metric))
        .filter((v): v is number => v !== null),
    );
  }

  return inRole.map((s) => ({
    playerId: s.playerId,
    lowSample: s.exposure < minimumForComparison,
    metrics: metricKeys.map((key) => {
      const metric = metricsByKey.get(key)!;
      const pool = pools.get(key)!;
      const value = valueOf(s, metric);
      return {
        metricKey: key,
        value,
        percentile: value === null ? null : percentileRank(value, pool, metric.higherIsBetter),
        poolSize: pool.length,
      };
    }),
  }));
}
