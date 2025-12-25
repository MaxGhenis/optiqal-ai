/**
 * Utilities for loading and processing precomputed profile data
 */

export interface ProfileResult {
  age: number;
  sex: "male" | "female";
  bmi_category: "underweight" | "normal" | "overweight" | "obese";
  smoking_status: "never" | "former" | "current";
  has_diabetes: boolean;
  has_hypertension: boolean;
  activity_level: "sedentary" | "light" | "moderate" | "active";
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
  intervention_effect_modifier: number;
  n_samples: number;
  discount_rate: number;
}

export interface ProfileData {
  id: string;
  name: string;
  category: string;
  description: string;
  results: Record<string, ProfileResult>;
}

/**
 * Load precomputed profile data for an intervention
 */
export async function loadProfileData(
  interventionId: string
): Promise<ProfileData | null> {
  try {
    const response = await fetch(`/precomputed/${interventionId}_profiles.json`);
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.error(`Failed to load profile data for ${interventionId}:`, error);
    return null;
  }
}

/**
 * Calculate BMI category from weight and height
 */
export function calculateBMICategory(
  weight: number,
  height: number
): ProfileResult["bmi_category"] {
  const bmi = weight / ((height / 100) ** 2);
  if (bmi < 18.5) return "underweight";
  if (bmi < 25) return "normal";
  if (bmi < 30) return "overweight";
  return "obese";
}

/**
 * Map smoking status to profile format
 */
export function mapSmokingStatus(
  smoker: boolean
): ProfileResult["smoking_status"] {
  return smoker ? "current" : "never";
}

/**
 * Find matching profile result for a user
 */
export function findMatchingProfile(
  profileData: ProfileData,
  age: number,
  sex: "male" | "female" | "other",
  bmiCategory: ProfileResult["bmi_category"],
  smokingStatus: ProfileResult["smoking_status"],
  hasDiabetes: boolean,
  hasHypertension: boolean
): ProfileResult | null {
  // Use male as fallback for "other"
  const profileSex = sex === "other" ? "male" : sex;

  // Build key
  const key = `${age}_${profileSex}_${bmiCategory}_${smokingStatus}_${hasDiabetes ? "diabetic" : "nondiabetic"}_${hasHypertension ? "hypertensive" : "normotensive"}`;

  return profileData.results[key] || null;
}

/**
 * Get all unique ages in the profile data
 */
export function getUniqueAges(profileData: ProfileData): number[] {
  const ages = new Set<number>();
  for (const key in profileData.results) {
    ages.add(profileData.results[key].age);
  }
  return Array.from(ages).sort((a, b) => a - b);
}

/**
 * Get all unique BMI categories in the profile data
 */
export function getUniqueBMICategories(
  profileData: ProfileData
): ProfileResult["bmi_category"][] {
  const categories = new Set<ProfileResult["bmi_category"]>();
  for (const key in profileData.results) {
    categories.add(profileData.results[key].bmi_category);
  }
  // Return in logical order
  const order: ProfileResult["bmi_category"][] = [
    "underweight",
    "normal",
    "overweight",
    "obese",
  ];
  return order.filter((cat) => categories.has(cat));
}

/**
 * Get all unique activity levels in the profile data
 */
export function getUniqueActivityLevels(
  profileData: ProfileData
): ProfileResult["activity_level"][] {
  const levels = new Set<ProfileResult["activity_level"]>();
  for (const key in profileData.results) {
    levels.add(profileData.results[key].activity_level);
  }
  // Return in logical order
  const order: ProfileResult["activity_level"][] = [
    "sedentary",
    "light",
    "moderate",
    "active",
  ];
  return order.filter((level) => levels.has(level));
}

/**
 * Build a heatmap grid for age vs BMI
 */
export function buildAgeByBMIGrid(
  profileData: ProfileData,
  sex: "male" | "female",
  smokingStatus: ProfileResult["smoking_status"],
  hasDiabetes: boolean,
  hasHypertension: boolean
): Array<{
  age: number;
  bmi_category: string;
  qaly: number;
}> {
  const ages = getUniqueAges(profileData);
  const bmiCategories = getUniqueBMICategories(profileData);

  const grid: Array<{
    age: number;
    bmi_category: string;
    qaly: number;
  }> = [];

  for (const age of ages) {
    for (const bmiCategory of bmiCategories) {
      const profile = findMatchingProfile(
        profileData,
        age,
        sex,
        bmiCategory,
        smokingStatus,
        hasDiabetes,
        hasHypertension
      );

      if (profile) {
        grid.push({
          age,
          bmi_category: bmiCategory,
          qaly: profile.qaly_median,
        });
      }
    }
  }

  return grid;
}

/**
 * Build activity level comparison data
 */
export function buildActivityLevelData(
  profileData: ProfileData,
  age: number,
  sex: "male" | "female",
  bmiCategory: ProfileResult["bmi_category"],
  smokingStatus: ProfileResult["smoking_status"],
  hasDiabetes: boolean,
  hasHypertension: boolean
): Array<{
  activity_level: string;
  qaly: number;
  qaly_ci_low: number;
  qaly_ci_high: number;
}> {
  const activityLevels = getUniqueActivityLevels(profileData);

  const data: Array<{
    activity_level: string;
    qaly: number;
    qaly_ci_low: number;
    qaly_ci_high: number;
  }> = [];

  for (const activityLevel of activityLevels) {
    // Find profile with this activity level
    const key = `${age}_${sex}_${bmiCategory}_${smokingStatus}_${hasDiabetes ? "diabetic" : "nondiabetic"}_${hasHypertension ? "hypertensive" : "normotensive"}`;
    const profile = profileData.results[key];

    if (profile && profile.activity_level === activityLevel) {
      data.push({
        activity_level: activityLevel,
        qaly: profile.qaly_median,
        qaly_ci_low: profile.qaly_ci95_low,
        qaly_ci_high: profile.qaly_ci95_high,
      });
    }
  }

  return data;
}
