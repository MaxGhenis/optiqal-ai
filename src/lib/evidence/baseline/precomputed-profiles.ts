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
 * Get baseline prediction by averaging across ALL matching profiles.
 *
 * When a field is unknown, we average across all possible values for that field.
 * This properly narrows the prediction as more information is provided.
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

  // Determine which values to iterate over for each field
  // If specified, use that value; if not, iterate over all possibilities
  const sexes = profile.sex && profile.sex !== "other"
    ? [profile.sex]
    : ["male", "female"];

  const bmiCategories = (profile.weight !== undefined && profile.height !== undefined)
    ? [getBMICategory(profile.weight, profile.height)]
    : [...BMI_CATEGORIES];

  const smokingStatuses = profile.smoker !== undefined
    ? [profile.smoker ? "current" : "never"] as SmokingStatus[]
    : [...SMOKING_STATUSES];

  const diabetesValues = profile.hasDiabetes !== undefined
    ? [profile.hasDiabetes]
    : [false, true];

  const hypertensionValues = profile.hasHypertension !== undefined
    ? [profile.hasHypertension]
    : [false, true];

  const activityLevels = profile.exerciseHoursPerWeek !== undefined
    ? [getActivityLevel(profile.exerciseHoursPerWeek)]
    : [...ACTIVITY_LEVELS];

  // Find bracketing ages for interpolation
  const lowerAge = AGES.filter((a) => a <= age).pop() ?? AGES[0];
  const upperAge = AGES.find((a) => a > age) ?? AGES[AGES.length - 1];
  const ageT = lowerAge === upperAge ? 0 : (age - lowerAge) / (upperAge - lowerAge);

  // Collect all matching profiles and average them
  let totalLifeYearsMedian = 0;
  let totalLifeYearsP5 = 0;
  let totalLifeYearsP95 = 0;
  let totalQalysMedian = 0;
  let count = 0;

  for (const sex of sexes) {
    for (const bmi of bmiCategories) {
      for (const smoking of smokingStatuses) {
        for (const diabetes of diabetesValues) {
          for (const hypertension of hypertensionValues) {
            for (const activity of activityLevels) {
              const lowerKey = buildProfileKey(
                lowerAge, sex, bmi, smoking, diabetes, hypertension, activity
              );
              const upperKey = buildProfileKey(
                upperAge, sex, bmi, smoking, diabetes, hypertension, activity
              );

              const lowerResult = data.results[lowerKey];
              const upperResult = data.results[upperKey];

              if (lowerResult) {
                // Interpolate between ages if we have both
                const lifeYearsMedian = upperResult && lowerAge !== upperAge
                  ? lowerResult.life_years_median * (1 - ageT) + upperResult.life_years_median * ageT
                  : lowerResult.life_years_median;
                const lifeYearsP5 = upperResult && lowerAge !== upperAge
                  ? lowerResult.life_years_p5 * (1 - ageT) + upperResult.life_years_p5 * ageT
                  : lowerResult.life_years_p5;
                const lifeYearsP95 = upperResult && lowerAge !== upperAge
                  ? lowerResult.life_years_p95 * (1 - ageT) + upperResult.life_years_p95 * ageT
                  : lowerResult.life_years_p95;
                const qalysMedian = upperResult && lowerAge !== upperAge
                  ? lowerResult.qalys_median * (1 - ageT) + upperResult.qalys_median * ageT
                  : lowerResult.qalys_median;

                totalLifeYearsMedian += lifeYearsMedian;
                totalLifeYearsP5 += lifeYearsP5;
                totalLifeYearsP95 += lifeYearsP95;
                totalQalysMedian += qalysMedian;
                count++;
              }
            }
          }
        }
      }
    }
  }

  if (count === 0) return null;

  return {
    lifeYearsMedian: totalLifeYearsMedian / count,
    lifeYearsP5: totalLifeYearsP5 / count,
    lifeYearsP95: totalLifeYearsP95 / count,
    qalysMedian: totalQalysMedian / count,
    interpolated: true,
  };
}
