/**
 * Precomputed Profile QALY Lookup
 *
 * Provides instant QALY estimates for any demographic profile by looking up
 * precomputed results. Supports interpolation for continuous variables (age, BMI).
 */

export type BmiCategory = "normal" | "overweight" | "obese" | "severely_obese";
export type SmokingStatus = "never" | "former" | "current";

export interface ProfileQuery {
  age: number;
  sex: "male" | "female";
  bmiCategory: BmiCategory;
  smokingStatus: SmokingStatus;
  hasDiabetes: boolean;
}

export interface ProfileResult {
  qalyMedian: number;
  qalyMean: number;
  qalyCi95Low: number;
  qalyCi95High: number;
  cvdContribution: number;
  cancerContribution: number;
  otherContribution: number;
  lifeYearsGained: number;
  causalFractionMean: number;
  baselineMortalityMultiplier: number;
}

interface PrecomputedProfileData {
  id: string;
  name: string;
  category: string;
  description: string | null;
  results: Record<string, RawProfileResult>;
  summary: {
    qaly_median_all: number;
    qaly_mean_all: number;
    qaly_min: number;
    qaly_max: number;
    qaly_std: number;
    n_profiles: number;
  };
  grid: {
    ages: number[];
    sexes: string[];
    bmi_categories: string[];
    smoking_statuses: string[];
    diabetes_statuses: boolean[];
  };
}

interface RawProfileResult {
  age: number;
  sex: string;
  bmi_category: string;
  smoking_status: string;
  has_diabetes: boolean;
  qaly_median: number;
  qaly_mean: number;
  qaly_ci95_low: number;
  qaly_ci95_high: number;
  cvd_contribution: number;
  cancer_contribution: number;
  other_contribution: number;
  life_years_gained: number;
  causal_fraction_mean: number;
  causal_fraction_ci95_low: number;
  causal_fraction_ci95_high: number;
  baseline_mortality_multiplier: number;
  n_samples: number;
  discount_rate: number;
}

// Cache for loaded profile data
const profileCache: Map<string, PrecomputedProfileData> = new Map();

/**
 * Generate profile key for lookup
 */
function makeProfileKey(
  age: number,
  sex: string,
  bmiCategory: string,
  smokingStatus: string,
  hasDiabetes: boolean
): string {
  const diabetesStr = hasDiabetes ? "diabetic" : "nondiabetic";
  return `${age}_${sex}_${bmiCategory}_${smokingStatus}_${diabetesStr}`;
}

/**
 * Convert raw result to typed result
 */
function convertResult(raw: RawProfileResult): ProfileResult {
  return {
    qalyMedian: raw.qaly_median,
    qalyMean: raw.qaly_mean,
    qalyCi95Low: raw.qaly_ci95_low,
    qalyCi95High: raw.qaly_ci95_high,
    cvdContribution: raw.cvd_contribution,
    cancerContribution: raw.cancer_contribution,
    otherContribution: raw.other_contribution,
    lifeYearsGained: raw.life_years_gained,
    causalFractionMean: raw.causal_fraction_mean,
    baselineMortalityMultiplier: raw.baseline_mortality_multiplier,
  };
}

/**
 * Interpolate between two results based on age fraction
 */
function interpolateResults(
  lower: ProfileResult,
  upper: ProfileResult,
  fraction: number
): ProfileResult {
  const lerp = (a: number, b: number) => a + (b - a) * fraction;

  return {
    qalyMedian: lerp(lower.qalyMedian, upper.qalyMedian),
    qalyMean: lerp(lower.qalyMean, upper.qalyMean),
    qalyCi95Low: lerp(lower.qalyCi95Low, upper.qalyCi95Low),
    qalyCi95High: lerp(lower.qalyCi95High, upper.qalyCi95High),
    cvdContribution: lerp(lower.cvdContribution, upper.cvdContribution),
    cancerContribution: lerp(lower.cancerContribution, upper.cancerContribution),
    otherContribution: lerp(lower.otherContribution, upper.otherContribution),
    lifeYearsGained: lerp(lower.lifeYearsGained, upper.lifeYearsGained),
    causalFractionMean: lerp(lower.causalFractionMean, upper.causalFractionMean),
    baselineMortalityMultiplier: lerp(
      lower.baselineMortalityMultiplier,
      upper.baselineMortalityMultiplier
    ),
  };
}

/**
 * Load precomputed profile data for an intervention
 */
export async function loadProfileData(
  interventionId: string
): Promise<PrecomputedProfileData | null> {
  // Check cache first
  if (profileCache.has(interventionId)) {
    return profileCache.get(interventionId)!;
  }

  try {
    const response = await fetch(
      `/precomputed/${interventionId}_profiles.json`
    );
    if (!response.ok) {
      console.warn(`Profile data not found for ${interventionId}`);
      return null;
    }

    const data: PrecomputedProfileData = await response.json();
    profileCache.set(interventionId, data);
    return data;
  } catch (error) {
    console.error(`Error loading profile data for ${interventionId}:`, error);
    return null;
  }
}

/**
 * Get QALY estimate for a specific profile
 *
 * Supports exact lookup for grid points and linear interpolation for ages
 * between grid points.
 */
export async function getProfileQALY(
  interventionId: string,
  query: ProfileQuery
): Promise<ProfileResult | null> {
  const data = await loadProfileData(interventionId);
  if (!data) return null;

  const { age, sex, bmiCategory, smokingStatus, hasDiabetes } = query;
  const ages = data.grid.ages;

  // Find surrounding ages for interpolation
  const lowerAgeIdx = ages.findIndex((a) => a > age) - 1;

  if (lowerAgeIdx < 0) {
    // Age below minimum - use minimum
    const key = makeProfileKey(ages[0], sex, bmiCategory, smokingStatus, hasDiabetes);
    const raw = data.results[key];
    return raw ? convertResult(raw) : null;
  }

  if (lowerAgeIdx >= ages.length - 1) {
    // Age above maximum - use maximum
    const key = makeProfileKey(
      ages[ages.length - 1],
      sex,
      bmiCategory,
      smokingStatus,
      hasDiabetes
    );
    const raw = data.results[key];
    return raw ? convertResult(raw) : null;
  }

  const lowerAge = ages[lowerAgeIdx];
  const upperAge = ages[lowerAgeIdx + 1];

  // Exact match - no interpolation needed
  if (age === lowerAge) {
    const key = makeProfileKey(lowerAge, sex, bmiCategory, smokingStatus, hasDiabetes);
    const raw = data.results[key];
    return raw ? convertResult(raw) : null;
  }

  // Interpolate between ages
  const lowerKey = makeProfileKey(lowerAge, sex, bmiCategory, smokingStatus, hasDiabetes);
  const upperKey = makeProfileKey(upperAge, sex, bmiCategory, smokingStatus, hasDiabetes);

  const lowerRaw = data.results[lowerKey];
  const upperRaw = data.results[upperKey];

  if (!lowerRaw || !upperRaw) {
    console.warn(`Missing profile data for interpolation: ${lowerKey} or ${upperKey}`);
    return lowerRaw ? convertResult(lowerRaw) : null;
  }

  const fraction = (age - lowerAge) / (upperAge - lowerAge);
  return interpolateResults(convertResult(lowerRaw), convertResult(upperRaw), fraction);
}

/**
 * Get BMI category from numeric BMI
 */
export function getBmiCategory(bmi: number): BmiCategory {
  if (bmi < 18.5) return "normal"; // Underweight treated as normal for now
  if (bmi < 25) return "normal";
  if (bmi < 30) return "overweight";
  if (bmi < 35) return "obese";
  return "severely_obese";
}

/**
 * Get QALY estimate from raw inputs
 *
 * Convenience function that converts BMI to category automatically.
 */
export async function getQALYForPerson(
  interventionId: string,
  age: number,
  sex: "male" | "female",
  bmi: number,
  smokingStatus: SmokingStatus,
  hasDiabetes: boolean
): Promise<ProfileResult | null> {
  return getProfileQALY(interventionId, {
    age,
    sex,
    bmiCategory: getBmiCategory(bmi),
    smokingStatus,
    hasDiabetes,
  });
}

/**
 * Get all available profile results for an intervention
 *
 * Useful for displaying heatmaps or summary statistics.
 */
export async function getAllProfileResults(
  interventionId: string
): Promise<Map<string, ProfileResult> | null> {
  const data = await loadProfileData(interventionId);
  if (!data) return null;

  const results = new Map<string, ProfileResult>();
  for (const [key, raw] of Object.entries(data.results)) {
    results.set(key, convertResult(raw));
  }
  return results;
}

/**
 * Get summary statistics for an intervention
 */
export async function getProfileSummary(interventionId: string): Promise<{
  medianQALY: number;
  minQALY: number;
  maxQALY: number;
  stdQALY: number;
  nProfiles: number;
} | null> {
  const data = await loadProfileData(interventionId);
  if (!data) return null;

  return {
    medianQALY: data.summary.qaly_median_all,
    minQALY: data.summary.qaly_min,
    maxQALY: data.summary.qaly_max,
    stdQALY: data.summary.qaly_std,
    nProfiles: data.summary.n_profiles,
  };
}
