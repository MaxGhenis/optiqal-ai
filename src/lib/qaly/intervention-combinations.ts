/**
 * Intervention Combination Module
 *
 * Combines multiple interventions with overlap corrections and diminishing returns.
 * Uses precomputed single-intervention QALYs for fast estimation.
 */

import { getProfileQALY, ProfileQuery, ProfileResult } from "./precomputed-profiles";

// =============================================================================
// OVERLAP MATRIX
// =============================================================================

/**
 * Overlap factors between intervention pairs.
 * Value represents fraction of second intervention's effect retained
 * when first is already applied (1.0 = fully additive, 0.0 = fully redundant).
 */
const OVERLAP_MATRIX: Record<string, Record<string, number>> = {
  // Exercise interventions overlap substantially
  walking_30min_daily: {
    daily_exercise_moderate: 0.4, // Walking is subset of moderate exercise
    strength_training: 0.8, // Different mechanisms
    sleep_8_hours: 0.9,
  },
  daily_exercise_moderate: {
    walking_30min_daily: 0.4,
    strength_training: 0.7,
    sleep_8_hours: 0.85,
  },
  strength_training: {
    walking_30min_daily: 0.8,
    daily_exercise_moderate: 0.7,
  },

  // Diet overlaps
  mediterranean_diet: {
    fish_oil_supplement: 0.5, // Mediterranean includes fish
  },
  fish_oil_supplement: {
    mediterranean_diet: 0.5,
  },

  // Stress/mental health overlaps
  meditation_daily: {
    sleep_8_hours: 0.8,
  },
  sleep_8_hours: {
    meditation_daily: 0.8,
    daily_exercise_moderate: 0.85,
    walking_30min_daily: 0.9,
  },
};

function getOverlapFactor(interventionA: string, interventionB: string): number {
  return OVERLAP_MATRIX[interventionA]?.[interventionB] ?? 1.0;
}

// =============================================================================
// DIMINISHING RETURNS
// =============================================================================

/**
 * Apply diminishing returns for stacking many interventions.
 * As baseline risk decreases, additional interventions have less room to benefit.
 */
function getDiminishingReturnsFactor(nInterventions: number): number {
  if (nInterventions <= 1) return 1.0;
  // Exponential decay with floor at 0.80
  return Math.max(0.95 ** (nInterventions - 1), 0.8);
}

// =============================================================================
// COMBINATION ESTIMATION
// =============================================================================

export interface CombinedEstimate {
  totalQaly: number;
  individualQalys: Record<string, number>;
  overlapAdjustments: Record<string, number>;
  diminishingReturnsFactor: number;
  interventionIds: string[];
}

/**
 * Estimate combined QALY from precomputed single-intervention QALYs.
 *
 * This is a fast approximation that:
 * 1. Sums individual QALY gains
 * 2. Applies overlap corrections for interventions with shared mechanisms
 * 3. Applies global diminishing returns for stacking many interventions
 */
export function estimateCombinedQaly(
  singleQalys: Record<string, number>,
  interventionIds: string[],
  options: {
    applyOverlap?: boolean;
    applyDiminishingReturns?: boolean;
  } = {}
): CombinedEstimate {
  const { applyOverlap = true, applyDiminishingReturns = true } = options;

  if (interventionIds.length === 0) {
    return {
      totalQaly: 0,
      individualQalys: {},
      overlapAdjustments: {},
      diminishingReturnsFactor: 1.0,
      interventionIds: [],
    };
  }

  const individualQalys: Record<string, number> = {};
  const overlapAdjustments: Record<string, number> = {};
  let totalQaly = 0;

  for (let i = 0; i < interventionIds.length; i++) {
    const intId = interventionIds[i];
    let qaly = singleQalys[intId] ?? 0;
    individualQalys[intId] = singleQalys[intId] ?? 0;

    if (applyOverlap && i > 0) {
      // Apply cumulative overlap from all previous interventions
      let cumulativeOverlap = 1.0;
      for (let j = 0; j < i; j++) {
        const prevId = interventionIds[j];
        const overlap = getOverlapFactor(prevId, intId);
        if (overlap < 1.0) {
          cumulativeOverlap *= overlap;
        }
      }
      if (cumulativeOverlap < 1.0) {
        overlapAdjustments[intId] = cumulativeOverlap;
        qaly *= cumulativeOverlap;
      }
    }

    totalQaly += qaly;
  }

  // Apply diminishing returns
  const drFactor = applyDiminishingReturns
    ? getDiminishingReturnsFactor(interventionIds.length)
    : 1.0;
  totalQaly *= drFactor;

  return {
    totalQaly,
    individualQalys,
    overlapAdjustments,
    diminishingReturnsFactor: drFactor,
    interventionIds,
  };
}

// =============================================================================
// PROFILE-BASED COMBINATION
// =============================================================================

/**
 * Get combined QALY estimate for a profile from precomputed data.
 *
 * Fetches single-intervention QALYs from precomputed files and combines them.
 */
export async function getCombinedProfileQaly(
  interventionIds: string[],
  query: ProfileQuery,
  options: {
    applyOverlap?: boolean;
    applyDiminishingReturns?: boolean;
  } = {}
): Promise<CombinedEstimate | null> {
  if (interventionIds.length === 0) {
    return {
      totalQaly: 0,
      individualQalys: {},
      overlapAdjustments: {},
      diminishingReturnsFactor: 1.0,
      interventionIds: [],
    };
  }

  // Fetch all single-intervention QALYs in parallel
  const results = await Promise.all(
    interventionIds.map(async (id) => {
      const result = await getProfileQALY(id, query);
      return { id, result };
    })
  );

  // Check if any failed
  const failed = results.filter((r) => r.result === null);
  if (failed.length > 0) {
    console.warn(
      `Missing precomputed data for: ${failed.map((f) => f.id).join(", ")}`
    );
    // Continue with available data
  }

  // Build single QALY map
  const singleQalys: Record<string, number> = {};
  for (const { id, result } of results) {
    if (result) {
      singleQalys[id] = result.qalyMedian;
    }
  }

  return estimateCombinedQaly(singleQalys, interventionIds, options);
}

// =============================================================================
// OPTIMAL PORTFOLIO
// =============================================================================

export interface PortfolioStep {
  interventionIds: string[];
  totalQaly: number;
  marginalQaly: number;
  addedIntervention: string;
}

/**
 * Find optimal intervention portfolio using greedy selection.
 *
 * At each step, adds the intervention with highest marginal QALY gain.
 * Returns the portfolio path showing cumulative gains.
 */
export function findOptimalPortfolio(
  singleQalys: Record<string, number>,
  maxInterventions: number = 5
): PortfolioStep[] {
  const available = new Set(Object.keys(singleQalys));
  const selected: string[] = [];
  const portfolioPath: PortfolioStep[] = [];

  for (let step = 0; step < Math.min(maxInterventions, available.size); step++) {
    let bestId: string | null = null;
    let bestMarginal = -Infinity;
    let bestTotal = 0;

    const currentTotal =
      selected.length > 0
        ? estimateCombinedQaly(singleQalys, selected).totalQaly
        : 0;

    for (const intId of available) {
      const candidate = [...selected, intId];
      const candidateTotal = estimateCombinedQaly(singleQalys, candidate).totalQaly;
      const marginal = candidateTotal - currentTotal;

      if (marginal > bestMarginal) {
        bestMarginal = marginal;
        bestId = intId;
        bestTotal = candidateTotal;
      }
    }

    if (bestId === null || bestMarginal <= 0) {
      break;
    }

    selected.push(bestId);
    available.delete(bestId);
    portfolioPath.push({
      interventionIds: [...selected],
      totalQaly: bestTotal,
      marginalQaly: bestMarginal,
      addedIntervention: bestId,
    });
  }

  return portfolioPath;
}

// =============================================================================
// INTERVENTION METADATA
// =============================================================================

/** Known intervention categories for overlap detection */
export const INTERVENTION_CATEGORIES: Record<string, string> = {
  walking_30min_daily: "exercise",
  daily_exercise_moderate: "exercise",
  strength_training: "exercise",
  mediterranean_diet: "diet",
  fish_oil_supplement: "supplement",
  quit_smoking: "smoking",
  moderate_alcohol: "alcohol",
  meditation_daily: "stress",
  sleep_8_hours: "sleep",
  daily_sunscreen: "skincare",
};

/**
 * Get interventions that don't overlap with already-selected ones.
 * Useful for suggesting non-redundant additions.
 */
export function getNonOverlappingInterventions(
  selected: string[],
  threshold: number = 0.7
): string[] {
  const all = Object.keys(INTERVENTION_CATEGORIES);

  return all.filter((intId) => {
    if (selected.includes(intId)) return false;

    // Check overlap with all selected interventions
    for (const selectedId of selected) {
      const overlap = getOverlapFactor(selectedId, intId);
      if (overlap < threshold) {
        return false; // Too much overlap
      }
    }
    return true;
  });
}
