/**
 * Precomputed Baseline Profiles
 *
 * Loads and queries precomputed baseline life expectancy from the
 * Python Markov model simulations.
 */

import type { PartialProfile } from "./partial-profile";

// Profile grid categories
const BMI_CATEGORIES = ["normal", "overweight", "obese", "severely_obese"] as const;
const SMOKING_STATUSES = ["never", "former", "current"] as const;
const ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active"] as const;
const AGES = [25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80] as const;

type BMICategory = (typeof BMI_CATEGORIES)[number];
type SmokingStatus = (typeof SMOKING_STATUSES)[number];
type ActivityLevel = (typeof ACTIVITY_LEVELS)[number];

interface PrecomputedBaseline {
  age: number;
  sex: string;
  bmi_category: string;
  smoking_status: string;
  has_diabetes: boolean;
  has_hypertension: boolean;
  activity_level: string;
  life_years_median: number;
  life_years_mean: number;
  life_years_p5: number;
  life_years_p95: number;
  qalys_median: number;
  qalys_mean: number;
  qalys_p5: number;
  qalys_p95: number;
  mortality_multiplier: number;
  n_samples: number;
  discount_rate: number;
}

interface PrecomputedData {
  version: string;
  description: string;
  n_profiles: number;
  n_samples: number;
  discount_rate: number;
  results: Record<string, PrecomputedBaseline>;
}

// Cache for loaded data
let cachedData: PrecomputedData | null = null;

/**
 * Load precomputed baseline profiles from JSON.
 */
export async function loadPrecomputedBaselines(): Promise<PrecomputedData> {
  if (cachedData) return cachedData;

  const response = await fetch("/precomputed/baseline_profiles.json");
  cachedData = await response.json();
  return cachedData!;
}

/**
 * Get BMI category from height/weight.
 */
function getBMICategory(weight?: number, height?: number): BMICategory {
  if (!weight || !height) return "normal"; // Default

  const heightM = height / 100;
  const bmi = weight / (heightM * heightM);

  if (bmi < 25) return "normal";
  if (bmi < 30) return "overweight";
  if (bmi < 35) return "obese";
  return "severely_obese";
}

/**
 * Get smoking status from profile.
 */
function getSmokingStatus(smoker?: boolean): SmokingStatus {
  if (smoker === undefined) return "never"; // Default
  return smoker ? "current" : "never";
}

/**
 * Get activity level from exercise hours.
 */
function getActivityLevel(exerciseHours?: number): ActivityLevel {
  if (exerciseHours === undefined) return "light"; // Default
  if (exerciseHours < 0.5) return "sedentary";
  if (exerciseHours < 2.5) return "light";
  if (exerciseHours < 5) return "moderate";
  return "active";
}

/**
 * Find nearest age in the grid.
 */
function getNearestAge(age: number): number {
  const gridAge = AGES.reduce((nearest, gridAge) =>
    Math.abs(gridAge - age) < Math.abs(nearest - age) ? gridAge : nearest
  );
  return gridAge;
}

/**
 * Build profile key for lookup.
 */
function buildProfileKey(
  age: number,
  sex: string,
  bmiCategory: BMICategory,
  smokingStatus: SmokingStatus,
  hasDiabetes: boolean,
  hasHypertension: boolean,
  activityLevel: ActivityLevel
): string {
  const diabetesStr = hasDiabetes ? "diabetic" : "nondiabetic";
  const hypertensionStr = hasHypertension ? "hypertensive" : "normotensive";
  return `${age}_${sex}_${bmiCategory}_${smokingStatus}_${diabetesStr}_${hypertensionStr}_${activityLevel}`;
}

/**
 * Look up precomputed baseline for a partial profile.
 *
 * Uses nearest-neighbor matching for continuous values like age.
 */
export async function getPrecomputedBaselineForProfile(
  profile: PartialProfile
): Promise<PrecomputedBaseline | null> {
  const data = await loadPrecomputedBaselines();

  // Map profile to grid values
  const age = getNearestAge(profile.age);
  const sex = profile.sex || "male";
  const bmiCategory = getBMICategory(profile.weight, profile.height);
  const smokingStatus = getSmokingStatus(profile.smoker);
  const hasDiabetes = profile.hasDiabetes ?? false;
  const hasHypertension = profile.hasHypertension ?? false;
  const activityLevel = getActivityLevel(profile.exerciseHoursPerWeek);

  const key = buildProfileKey(
    age,
    sex,
    bmiCategory,
    smokingStatus,
    hasDiabetes,
    hasHypertension,
    activityLevel
  );

  return data.results[key] || null;
}

/**
 * Get baseline for a specific sex with age interpolation.
 */
async function getBaselineForSex(
  data: PrecomputedData,
  age: number,
  sex: string,
  bmiCategory: BMICategory,
  smokingStatus: SmokingStatus,
  hasDiabetes: boolean,
  hasHypertension: boolean,
  activityLevel: ActivityLevel
): Promise<{
  lifeYearsMedian: number;
  lifeYearsP5: number;
  lifeYearsP95: number;
  qalysMedian: number;
} | null> {
  // Find bracketing ages
  const lowerAge = AGES.filter((a) => a <= age).pop() ?? AGES[0];
  const upperAge = AGES.find((a) => a > age) ?? AGES[AGES.length - 1];

  const lowerKey = buildProfileKey(
    lowerAge,
    sex,
    bmiCategory,
    smokingStatus,
    hasDiabetes,
    hasHypertension,
    activityLevel
  );
  const upperKey = buildProfileKey(
    upperAge,
    sex,
    bmiCategory,
    smokingStatus,
    hasDiabetes,
    hasHypertension,
    activityLevel
  );

  const lowerResult = data.results[lowerKey];
  const upperResult = data.results[upperKey];

  if (!lowerResult) return null;

  // If exact match or no upper bound, return lower
  if (lowerAge === age || lowerAge === upperAge || !upperResult) {
    return {
      lifeYearsMedian: lowerResult.life_years_median,
      lifeYearsP5: lowerResult.life_years_p5,
      lifeYearsP95: lowerResult.life_years_p95,
      qalysMedian: lowerResult.qalys_median,
    };
  }

  // Linear interpolation
  const t = (age - lowerAge) / (upperAge - lowerAge);

  return {
    lifeYearsMedian:
      lowerResult.life_years_median * (1 - t) +
      upperResult.life_years_median * t,
    lifeYearsP5:
      lowerResult.life_years_p5 * (1 - t) + upperResult.life_years_p5 * t,
    lifeYearsP95:
      lowerResult.life_years_p95 * (1 - t) + upperResult.life_years_p95 * t,
    qalysMedian:
      lowerResult.qalys_median * (1 - t) + upperResult.qalys_median * t,
  };
}

/**
 * Get baseline prediction with interpolation for non-grid ages.
 *
 * For ages between grid points, linearly interpolates between
 * the two nearest grid ages.
 *
 * When sex is not specified, averages male and female predictions.
 */
export async function getInterpolatedBaseline(
  profile: PartialProfile
): Promise<{
  lifeYearsMedian: number;
  lifeYearsP5: number;
  lifeYearsP95: number;
  qalysMedian: number;
  interpolated: boolean;
} | null> {
  const data = await loadPrecomputedBaselines();

  const age = profile.age;
  const bmiCategory = getBMICategory(profile.weight, profile.height);
  const smokingStatus = getSmokingStatus(profile.smoker);
  const hasDiabetes = profile.hasDiabetes ?? false;
  const hasHypertension = profile.hasHypertension ?? false;
  const activityLevel = getActivityLevel(profile.exerciseHoursPerWeek);

  // If sex is specified, get result for that sex
  if (profile.sex && profile.sex !== "other") {
    const result = await getBaselineForSex(
      data,
      age,
      profile.sex,
      bmiCategory,
      smokingStatus,
      hasDiabetes,
      hasHypertension,
      activityLevel
    );
    return result ? { ...result, interpolated: true } : null;
  }

  // Sex not specified - average male and female (50/50)
  const maleResult = await getBaselineForSex(
    data,
    age,
    "male",
    bmiCategory,
    smokingStatus,
    hasDiabetes,
    hasHypertension,
    activityLevel
  );
  const femaleResult = await getBaselineForSex(
    data,
    age,
    "female",
    bmiCategory,
    smokingStatus,
    hasDiabetes,
    hasHypertension,
    activityLevel
  );

  if (!maleResult || !femaleResult) {
    return maleResult || femaleResult
      ? { ...(maleResult || femaleResult)!, interpolated: true }
      : null;
  }

  // Average male and female predictions
  return {
    lifeYearsMedian: (maleResult.lifeYearsMedian + femaleResult.lifeYearsMedian) / 2,
    lifeYearsP5: (maleResult.lifeYearsP5 + femaleResult.lifeYearsP5) / 2,
    lifeYearsP95: (maleResult.lifeYearsP95 + femaleResult.lifeYearsP95) / 2,
    qalysMedian: (maleResult.qalysMedian + femaleResult.qalysMedian) / 2,
    interpolated: true,
  };
}
