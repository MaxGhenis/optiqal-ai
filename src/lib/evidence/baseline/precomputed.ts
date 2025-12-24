/**
 * Precomputed baseline data loader
 *
 * Loads pre-tabulated life expectancy and QALY data for O(1) lookups
 * instead of runtime interpolation.
 */

export interface PrecomputedBaselines {
  metadata: {
    version: string;
    source: string;
    discount_rate: number;
    max_age: number;
  };
  life_expectancy: {
    male: Record<string, number>;
    female: Record<string, number>;
  };
  remaining_qalys: {
    male: Record<string, number>;
    female: Record<string, number>;
  };
  cause_fractions: Record<
    string,
    {
      cvd: number;
      cancer: number;
      other: number;
    }
  >;
  quality_weights: Record<string, number>;
}

let cachedBaselines: PrecomputedBaselines | null = null;

/**
 * Load precomputed baselines from JSON file
 * Cached after first load
 */
export async function loadPrecomputedBaselines(): Promise<PrecomputedBaselines> {
  if (cachedBaselines) {
    return cachedBaselines;
  }

  // In browser/Next.js, fetch from public directory
  const response = await fetch("/precomputed/baselines.json");
  if (!response.ok) {
    throw new Error("Failed to load precomputed baselines");
  }

  cachedBaselines = await response.json();
  return cachedBaselines;
}

/**
 * Get precomputed remaining life expectancy
 * Returns null if not available (age out of range)
 */
export function getPrecomputedLifeExpectancy(
  age: number,
  sex: "male" | "female" | "other",
  baselines: PrecomputedBaselines
): number | null {
  const roundedAge = Math.round(age);

  if (roundedAge < 0 || roundedAge > 100) {
    return null;
  }

  if (sex === "other") {
    // Average male and female
    const male = baselines.life_expectancy.male[roundedAge.toString()];
    const female = baselines.life_expectancy.female[roundedAge.toString()];
    return (male + female) / 2;
  }

  return baselines.life_expectancy[sex][roundedAge.toString()] ?? null;
}

/**
 * Get precomputed remaining QALYs (3% discount rate)
 * Returns null if not available
 */
export function getPrecomputedRemainingQALYs(
  age: number,
  sex: "male" | "female" | "other",
  baselines: PrecomputedBaselines
): number | null {
  const roundedAge = Math.round(age);

  if (roundedAge < 0 || roundedAge > 100) {
    return null;
  }

  if (sex === "other") {
    // Average male and female
    const male = baselines.remaining_qalys.male[roundedAge.toString()];
    const female = baselines.remaining_qalys.female[roundedAge.toString()];
    return (male + female) / 2;
  }

  return baselines.remaining_qalys[sex][roundedAge.toString()] ?? null;
}

/**
 * Get precomputed cause fractions for an age
 */
export function getPrecomputedCauseFractions(
  age: number,
  baselines: PrecomputedBaselines
): { cvd: number; cancer: number; other: number } | null {
  const roundedAge = Math.round(age);

  if (roundedAge < 0 || roundedAge > 100) {
    return null;
  }

  return baselines.cause_fractions[roundedAge.toString()] ?? null;
}

/**
 * Get precomputed quality weight for an age
 */
export function getPrecomputedQualityWeight(
  age: number,
  baselines: PrecomputedBaselines
): number | null {
  const roundedAge = Math.round(age);

  if (roundedAge < 0 || roundedAge > 100) {
    return null;
  }

  return baselines.quality_weights[roundedAge.toString()] ?? null;
}
