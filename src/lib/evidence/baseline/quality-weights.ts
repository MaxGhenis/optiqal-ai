/**
 * Health-related quality of life weights
 *
 * Sources:
 * - GBD 2019 Disability Weights: https://ghdx.healthdata.org/record/ihme-data/gbd-2019-disability-weights
 * - WHO HALE: https://www.who.int/data/gho/data/indicators/indicator-details/GHO/healthy-life-expectancy-(hale)-at-birth
 * - EQ-5D population norms: Various studies
 *
 * Quality weight of 1.0 = perfect health
 * Quality weight of 0.0 = death-equivalent state
 */

/**
 * Average quality weight by age
 * Based on EQ-5D-5L population norms (US/UK averaged)
 * Accounts for typical age-related health decline
 */
export const AGE_QUALITY_WEIGHTS: { age: number; weight: number }[] = [
  { age: 0, weight: 0.93 },
  { age: 10, weight: 0.95 },
  { age: 20, weight: 0.94 },
  { age: 30, weight: 0.92 },
  { age: 40, weight: 0.89 },
  { age: 50, weight: 0.85 },
  { age: 60, weight: 0.80 },
  { age: 70, weight: 0.74 },
  { age: 80, weight: 0.66 },
  { age: 90, weight: 0.55 },
];

/**
 * GBD 2019 Disability Weights for common conditions
 * These reduce quality of life from baseline
 */
export const CONDITION_DISABILITY_WEIGHTS: Record<
  string,
  { weight: number; source: string }
> = {
  // Cardiovascular
  heart_failure_mild: {
    weight: 0.041,
    source: "GBD 2019: Heart failure, mild",
  },
  heart_failure_moderate: {
    weight: 0.072,
    source: "GBD 2019: Heart failure, moderate",
  },
  heart_failure_severe: {
    weight: 0.179,
    source: "GBD 2019: Heart failure, severe",
  },
  angina_mild: { weight: 0.033, source: "GBD 2019: Angina pectoris, mild" },
  angina_moderate: {
    weight: 0.08,
    source: "GBD 2019: Angina pectoris, moderate",
  },
  angina_severe: { weight: 0.167, source: "GBD 2019: Angina pectoris, severe" },

  // Diabetes
  diabetes_uncomplicated: {
    weight: 0.049,
    source: "GBD 2019: Diabetes mellitus, uncomplicated",
  },
  diabetes_neuropathy: {
    weight: 0.133,
    source: "GBD 2019: Diabetic neuropathy",
  },
  diabetes_retinopathy: {
    weight: 0.033,
    source: "GBD 2019: Diabetic retinopathy, mild",
  },

  // Respiratory
  copd_mild: { weight: 0.019, source: "GBD 2019: COPD, mild" },
  copd_moderate: { weight: 0.225, source: "GBD 2019: COPD, moderate" },
  copd_severe: { weight: 0.408, source: "GBD 2019: COPD, severe" },
  asthma_controlled: { weight: 0.015, source: "GBD 2019: Asthma, controlled" },
  asthma_uncontrolled: {
    weight: 0.133,
    source: "GBD 2019: Asthma, uncontrolled",
  },

  // Mental health
  depression_mild: {
    weight: 0.145,
    source: "GBD 2019: Major depressive disorder, mild",
  },
  depression_moderate: {
    weight: 0.396,
    source: "GBD 2019: Major depressive disorder, moderate",
  },
  depression_severe: {
    weight: 0.658,
    source: "GBD 2019: Major depressive disorder, severe",
  },
  anxiety_mild: {
    weight: 0.03,
    source: "GBD 2019: Anxiety disorders, mild",
  },
  anxiety_moderate: {
    weight: 0.133,
    source: "GBD 2019: Anxiety disorders, moderate",
  },
  anxiety_severe: {
    weight: 0.523,
    source: "GBD 2019: Anxiety disorders, severe",
  },

  // Musculoskeletal
  back_pain_mild: { weight: 0.02, source: "GBD 2019: Low back pain, mild" },
  back_pain_moderate: {
    weight: 0.054,
    source: "GBD 2019: Low back pain, moderate",
  },
  back_pain_severe: {
    weight: 0.325,
    source: "GBD 2019: Low back pain, severe",
  },
  osteoarthritis_mild: {
    weight: 0.023,
    source: "GBD 2019: Osteoarthritis, mild",
  },
  osteoarthritis_moderate: {
    weight: 0.079,
    source: "GBD 2019: Osteoarthritis, moderate",
  },
  osteoarthritis_severe: {
    weight: 0.165,
    source: "GBD 2019: Osteoarthritis, severe",
  },

  // Cancer (generic, during treatment)
  cancer_diagnosis: {
    weight: 0.288,
    source: "GBD 2019: Generic cancer, diagnosis/treatment",
  },
  cancer_remission: { weight: 0.049, source: "GBD 2019: Generic cancer, remission" },
  cancer_terminal: {
    weight: 0.54,
    source: "GBD 2019: Terminal phase cancer",
  },

  // Obesity-related
  obesity_class1: {
    weight: 0.025,
    source: "Estimated from EQ-5D studies, BMI 30-35",
  },
  obesity_class2: {
    weight: 0.05,
    source: "Estimated from EQ-5D studies, BMI 35-40",
  },
  obesity_class3: {
    weight: 0.1,
    source: "Estimated from EQ-5D studies, BMI 40+",
  },
};

/**
 * Get baseline quality weight for age (linear interpolation)
 */
export function getAgeQualityWeight(age: number): number {
  const clampedAge = Math.max(0, Math.min(90, age));

  let lower = AGE_QUALITY_WEIGHTS[0];
  let upper = AGE_QUALITY_WEIGHTS[AGE_QUALITY_WEIGHTS.length - 1];

  for (let i = 0; i < AGE_QUALITY_WEIGHTS.length - 1; i++) {
    if (
      AGE_QUALITY_WEIGHTS[i].age <= clampedAge &&
      AGE_QUALITY_WEIGHTS[i + 1].age > clampedAge
    ) {
      lower = AGE_QUALITY_WEIGHTS[i];
      upper = AGE_QUALITY_WEIGHTS[i + 1];
      break;
    }
  }

  const t = (clampedAge - lower.age) / (upper.age - lower.age || 1);
  return lower.weight + t * (upper.weight - lower.weight);
}

/**
 * Calculate combined quality weight with conditions
 * Uses multiplicative model: Q_total = Q_age × (1 - DW1) × (1 - DW2) × ...
 */
export function getQualityWeightWithConditions(
  age: number,
  conditionKeys: string[]
): number {
  let weight = getAgeQualityWeight(age);

  for (const key of conditionKeys) {
    const condition = CONDITION_DISABILITY_WEIGHTS[key];
    if (condition) {
      weight *= 1 - condition.weight;
    }
  }

  return Math.max(0, weight);
}
