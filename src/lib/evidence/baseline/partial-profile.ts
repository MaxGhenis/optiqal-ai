/**
 * Partial Profile & Population Distributions
 *
 * Handles incomplete user profiles by sampling unknown attributes
 * from population distributions. As users provide more information,
 * the prediction interval shrinks because we condition on more data.
 *
 * Data sources:
 * - NHANES 2017-2020 for BMI, exercise, sleep distributions
 * - CDC BRFSS for smoking prevalence
 * - Census/life tables for age/sex distributions
 */

import type { UserProfile } from "@/types";

/**
 * Partial profile where only age is required.
 * All other fields are optional - when missing, we sample from
 * population distributions to propagate uncertainty.
 */
export interface PartialProfile {
  // Required - minimum for any prediction
  age: number;

  // Core demographics (high impact on prediction)
  sex?: "male" | "female" | "other";

  // Body composition
  weight?: number; // kg
  height?: number; // cm

  // Lifestyle factors
  smoker?: boolean;
  exerciseHoursPerWeek?: number;
  sleepHoursPerNight?: number;

  // Health conditions
  hasDiabetes?: boolean;
  hasHypertension?: boolean;

  // Less critical for mortality but included
  diet?: "omnivore" | "vegetarian" | "vegan" | "pescatarian" | "keto" | "other";
  activityLevel?: "sedentary" | "light" | "moderate" | "active";
}

/**
 * Population distribution for a continuous variable
 */
interface ContinuousDistribution {
  mean: number;
  sd: number;
  min?: number;
  max?: number;
}

/**
 * Population distribution for BMI by age and sex
 * Source: NHANES 2017-2020
 */
const BMI_DISTRIBUTIONS: Record<string, Record<string, ContinuousDistribution>> = {
  male: {
    "18-24": { mean: 26.2, sd: 5.8, min: 15, max: 50 },
    "25-34": { mean: 28.4, sd: 6.1, min: 15, max: 55 },
    "35-44": { mean: 29.4, sd: 6.0, min: 15, max: 55 },
    "45-54": { mean: 29.8, sd: 5.9, min: 15, max: 55 },
    "55-64": { mean: 30.0, sd: 5.8, min: 15, max: 55 },
    "65-74": { mean: 29.5, sd: 5.5, min: 15, max: 50 },
    "75+": { mean: 27.8, sd: 5.0, min: 15, max: 45 },
  },
  female: {
    "18-24": { mean: 27.0, sd: 7.2, min: 15, max: 55 },
    "25-34": { mean: 29.2, sd: 7.8, min: 15, max: 60 },
    "35-44": { mean: 30.1, sd: 7.9, min: 15, max: 60 },
    "45-54": { mean: 30.4, sd: 7.6, min: 15, max: 60 },
    "55-64": { mean: 30.5, sd: 7.3, min: 15, max: 55 },
    "65-74": { mean: 30.0, sd: 6.8, min: 15, max: 50 },
    "75+": { mean: 28.2, sd: 6.0, min: 15, max: 45 },
  },
};

/**
 * Exercise hours per week distribution
 * Source: NHANES Physical Activity data
 * Note: Highly right-skewed - many people exercise 0, few exercise a lot
 */
const EXERCISE_DISTRIBUTION: Record<string, ContinuousDistribution> = {
  "18-34": { mean: 3.2, sd: 4.5, min: 0, max: 20 },
  "35-54": { mean: 2.5, sd: 3.8, min: 0, max: 20 },
  "55-74": { mean: 2.0, sd: 3.2, min: 0, max: 15 },
  "75+": { mean: 1.2, sd: 2.5, min: 0, max: 10 },
};

/**
 * Sleep hours per night distribution
 * Source: NHANES Sleep data
 */
const SLEEP_DISTRIBUTION: ContinuousDistribution = {
  mean: 7.0,
  sd: 1.3,
  min: 3,
  max: 12,
};

/**
 * Smoking prevalence by age group
 * Source: CDC BRFSS 2022
 */
const SMOKING_PREVALENCE: Record<string, number> = {
  "18-24": 0.08,
  "25-34": 0.12,
  "35-44": 0.14,
  "45-54": 0.15,
  "55-64": 0.14,
  "65-74": 0.09,
  "75+": 0.05,
};

/**
 * Diabetes prevalence by age
 * Source: CDC National Diabetes Statistics Report 2022
 */
const DIABETES_PREVALENCE: Record<string, number> = {
  "18-44": 0.04,
  "45-64": 0.14,
  "65+": 0.27,
};

/**
 * Hypertension prevalence by age
 * Source: CDC NHANES 2017-2020
 */
const HYPERTENSION_PREVALENCE: Record<string, number> = {
  "18-39": 0.22,
  "40-59": 0.45,
  "60+": 0.74,
};

/**
 * Get age bucket for distribution lookup
 */
function getAgeBucket(age: number, buckets: string[]): string {
  for (const bucket of buckets) {
    if (bucket.includes("+")) {
      const min = parseInt(bucket.replace("+", ""));
      if (age >= min) return bucket;
    } else if (bucket.includes("-")) {
      const [min, max] = bucket.split("-").map(Number);
      if (age >= min && age <= max) return bucket;
    }
  }
  return buckets[buckets.length - 1]; // Default to last bucket
}

/**
 * Sample from a truncated normal distribution
 */
function sampleTruncatedNormal(
  dist: ContinuousDistribution,
  rng: () => number
): number {
  // Box-Muller transform
  const u1 = rng();
  const u2 = rng();
  const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  let value = dist.mean + z * dist.sd;

  // Truncate to bounds
  if (dist.min !== undefined) value = Math.max(dist.min, value);
  if (dist.max !== undefined) value = Math.min(dist.max, value);

  return value;
}

/**
 * Sample a complete profile from a partial profile
 * Unknown fields are sampled from population distributions
 */
export function sampleCompleteProfile(
  partial: PartialProfile,
  rng: () => number
): UserProfile {
  const age = partial.age;

  // Sex: 50/50 if unknown
  const sex = partial.sex ?? (rng() < 0.5 ? "male" : "female");

  // BMI -> height and weight
  let height: number;
  let weight: number;

  if (partial.height !== undefined && partial.weight !== undefined) {
    height = partial.height;
    weight = partial.weight;
  } else {
    // Sample BMI from distribution
    const bmiBuckets = Object.keys(BMI_DISTRIBUTIONS[sex === "female" ? "female" : "male"]);
    const bmiBucket = getAgeBucket(age, bmiBuckets);
    const bmiDist = BMI_DISTRIBUTIONS[sex === "female" ? "female" : "male"][bmiBucket];
    const bmi = sampleTruncatedNormal(bmiDist, rng);

    if (partial.height !== undefined) {
      // Have height, derive weight from sampled BMI
      height = partial.height;
      weight = bmi * Math.pow(height / 100, 2);
    } else if (partial.weight !== undefined) {
      // Have weight, derive height from sampled BMI
      weight = partial.weight;
      height = 100 * Math.sqrt(weight / bmi);
    } else {
      // Neither - sample typical height, then derive weight
      const avgHeight = sex === "female" ? 162 : 176; // cm
      const heightSd = sex === "female" ? 6.5 : 7.0;
      height = sampleTruncatedNormal(
        { mean: avgHeight, sd: heightSd, min: 140, max: 210 },
        rng
      );
      weight = bmi * Math.pow(height / 100, 2);
    }
  }

  // Exercise
  let exerciseHoursPerWeek: number;
  if (partial.exerciseHoursPerWeek !== undefined) {
    exerciseHoursPerWeek = partial.exerciseHoursPerWeek;
  } else {
    const exBuckets = Object.keys(EXERCISE_DISTRIBUTION);
    const exBucket = getAgeBucket(age, exBuckets);
    const exDist = EXERCISE_DISTRIBUTION[exBucket];
    exerciseHoursPerWeek = Math.max(0, sampleTruncatedNormal(exDist, rng));
  }

  // Sleep
  const sleepHoursPerNight =
    partial.sleepHoursPerNight ?? sampleTruncatedNormal(SLEEP_DISTRIBUTION, rng);

  // Smoking
  let smoker: boolean;
  if (partial.smoker !== undefined) {
    smoker = partial.smoker;
  } else {
    const smokeBuckets = Object.keys(SMOKING_PREVALENCE);
    const smokeBucket = getAgeBucket(age, smokeBuckets);
    smoker = rng() < SMOKING_PREVALENCE[smokeBucket];
  }

  // Diabetes
  let hasDiabetes: boolean;
  if (partial.hasDiabetes !== undefined) {
    hasDiabetes = partial.hasDiabetes;
  } else {
    const diabetesBuckets = Object.keys(DIABETES_PREVALENCE);
    const diabetesBucket = getAgeBucket(age, diabetesBuckets);
    hasDiabetes = rng() < DIABETES_PREVALENCE[diabetesBucket];
  }

  // Hypertension
  let hasHypertension: boolean;
  if (partial.hasHypertension !== undefined) {
    hasHypertension = partial.hasHypertension;
  } else {
    const htBuckets = Object.keys(HYPERTENSION_PREVALENCE);
    const htBucket = getAgeBucket(age, htBuckets);
    hasHypertension = rng() < HYPERTENSION_PREVALENCE[htBucket];
  }

  // Derive activity level from exercise hours
  let activityLevel: UserProfile["activityLevel"];
  if (partial.activityLevel !== undefined) {
    activityLevel = partial.activityLevel;
  } else {
    if (exerciseHoursPerWeek < 0.5) activityLevel = "sedentary";
    else if (exerciseHoursPerWeek < 2.5) activityLevel = "light";
    else if (exerciseHoursPerWeek < 5) activityLevel = "moderate";
    else activityLevel = "active";
  }

  return {
    age,
    sex: sex === "other" ? "male" : sex, // Default "other" to male for calculations
    weight,
    height,
    smoker,
    exerciseHoursPerWeek,
    sleepHoursPerNight,
    existingConditions: [],
    diet: partial.diet ?? "omnivore",
    hasDiabetes,
    hasHypertension,
    activityLevel,
  };
}

/**
 * Calculate "completeness" score - how much of the profile is known
 * Returns 0-1 where 1 means all fields provided
 *
 * Weights reflect relative importance for prediction precision:
 * - Age: always known (required)
 * - Sex: high impact on life expectancy
 * - Smoking: very high impact
 * - BMI (weight+height): moderate-high impact
 * - Exercise: moderate impact
 * - Sleep: low-moderate impact
 * - Conditions: moderate impact
 */
export function calculateProfileCompleteness(partial: PartialProfile): number {
  const weights = {
    sex: 0.15,
    smoker: 0.25,
    weightHeight: 0.20, // Combined
    exercise: 0.15,
    sleep: 0.05,
    diabetes: 0.10,
    hypertension: 0.10,
  };

  let score = 0;

  if (partial.sex !== undefined) score += weights.sex;
  if (partial.smoker !== undefined) score += weights.smoker;
  if (partial.weight !== undefined && partial.height !== undefined) {
    score += weights.weightHeight;
  } else if (partial.weight !== undefined || partial.height !== undefined) {
    score += weights.weightHeight * 0.5; // Partial credit
  }
  if (partial.exerciseHoursPerWeek !== undefined) score += weights.exercise;
  if (partial.sleepHoursPerNight !== undefined) score += weights.sleep;
  if (partial.hasDiabetes !== undefined) score += weights.diabetes;
  if (partial.hasHypertension !== undefined) score += weights.hypertension;

  return score;
}

/**
 * Get list of missing fields with their impact on precision
 */
export function getMissingFields(partial: PartialProfile): Array<{
  field: string;
  label: string;
  impactPercent: number;
}> {
  const fields: Array<{ field: string; label: string; impactPercent: number }> = [];

  if (partial.sex === undefined) {
    fields.push({ field: "sex", label: "Sex", impactPercent: 15 });
  }
  if (partial.smoker === undefined) {
    fields.push({ field: "smoker", label: "Smoking status", impactPercent: 25 });
  }
  if (partial.weight === undefined || partial.height === undefined) {
    fields.push({ field: "bmi", label: "Height & weight", impactPercent: 20 });
  }
  if (partial.exerciseHoursPerWeek === undefined) {
    fields.push({ field: "exercise", label: "Exercise habits", impactPercent: 15 });
  }
  if (partial.hasDiabetes === undefined) {
    fields.push({ field: "diabetes", label: "Diabetes status", impactPercent: 10 });
  }
  if (partial.hasHypertension === undefined) {
    fields.push({ field: "hypertension", label: "Blood pressure", impactPercent: 10 });
  }
  if (partial.sleepHoursPerNight === undefined) {
    fields.push({ field: "sleep", label: "Sleep habits", impactPercent: 5 });
  }

  // Sort by impact (highest first)
  return fields.sort((a, b) => b.impactPercent - a.impactPercent);
}

/**
 * Convert PartialProfile to full UserProfile using population means
 * (for point estimates when we don't want to run Monte Carlo)
 */
export function partialToMeanProfile(partial: PartialProfile): UserProfile {
  const age = partial.age;
  const sex = partial.sex ?? "male";

  // Use population means for missing values
  const bmiBuckets = Object.keys(BMI_DISTRIBUTIONS[sex === "female" ? "female" : "male"]);
  const bmiBucket = getAgeBucket(age, bmiBuckets);
  const bmiDist = BMI_DISTRIBUTIONS[sex === "female" ? "female" : "male"][bmiBucket];

  let height: number;
  let weight: number;

  if (partial.height !== undefined && partial.weight !== undefined) {
    height = partial.height;
    weight = partial.weight;
  } else {
    const avgHeight = sex === "female" ? 162 : 176;
    height = partial.height ?? avgHeight;
    const bmi = bmiDist.mean;
    weight = partial.weight ?? bmi * Math.pow(height / 100, 2);
  }

  const exBuckets = Object.keys(EXERCISE_DISTRIBUTION);
  const exBucket = getAgeBucket(age, exBuckets);

  const smokeBuckets = Object.keys(SMOKING_PREVALENCE);
  const smokeBucket = getAgeBucket(age, smokeBuckets);

  const exerciseHoursPerWeek =
    partial.exerciseHoursPerWeek ?? EXERCISE_DISTRIBUTION[exBucket].mean;

  let activityLevel: UserProfile["activityLevel"];
  if (partial.activityLevel !== undefined) {
    activityLevel = partial.activityLevel;
  } else {
    if (exerciseHoursPerWeek < 0.5) activityLevel = "sedentary";
    else if (exerciseHoursPerWeek < 2.5) activityLevel = "light";
    else if (exerciseHoursPerWeek < 5) activityLevel = "moderate";
    else activityLevel = "active";
  }

  return {
    age,
    sex: sex === "other" ? "male" : sex,
    weight,
    height,
    smoker: partial.smoker ?? SMOKING_PREVALENCE[smokeBucket] > 0.5,
    exerciseHoursPerWeek,
    sleepHoursPerNight: partial.sleepHoursPerNight ?? SLEEP_DISTRIBUTION.mean,
    existingConditions: [],
    diet: partial.diet ?? "omnivore",
    hasDiabetes: partial.hasDiabetes ?? false, // Default to no for mean profile
    hasHypertension: partial.hasHypertension ?? false,
    activityLevel,
  };
}
