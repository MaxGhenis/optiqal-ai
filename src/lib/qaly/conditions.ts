/**
 * Condition-specific data for QALY calculations
 *
 * Sources:
 * - GBD 2019 for disability weights
 * - GBD 2019 for baseline incidence rates
 * - EQ-5D-5L tariffs for dimension mappings
 */

import type { HealthCondition } from "./types";

/**
 * Disability weights by condition and severity
 * From GBD 2019
 */
export const DISABILITY_WEIGHTS: Record<
  HealthCondition,
  { mild: number; moderate: number; severe: number; source: string }
> = {
  // Cardiovascular
  heart_failure: {
    mild: 0.041,
    moderate: 0.072,
    severe: 0.179,
    source: "GBD 2019",
  },
  angina: {
    mild: 0.033,
    moderate: 0.08,
    severe: 0.167,
    source: "GBD 2019",
  },
  stroke: {
    mild: 0.019,
    moderate: 0.07,
    severe: 0.316,
    source: "GBD 2019 (long-term)",
  },
  hypertension: {
    mild: 0.0,
    moderate: 0.0,
    severe: 0.0,
    source: "GBD 2019 (asymptomatic)",
  },

  // Metabolic
  diabetes: {
    mild: 0.049,
    moderate: 0.133,
    severe: 0.288,
    source: "GBD 2019",
  },
  obesity: {
    mild: 0.025,
    moderate: 0.05,
    severe: 0.1,
    source: "EQ-5D studies",
  },

  // Respiratory
  copd: {
    mild: 0.019,
    moderate: 0.225,
    severe: 0.408,
    source: "GBD 2019",
  },
  asthma: {
    mild: 0.015,
    moderate: 0.133,
    severe: 0.133,
    source: "GBD 2019",
  },

  // Mental health
  depression: {
    mild: 0.145,
    moderate: 0.396,
    severe: 0.658,
    source: "GBD 2019",
  },
  anxiety: {
    mild: 0.03,
    moderate: 0.133,
    severe: 0.523,
    source: "GBD 2019",
  },
  cognitive_impairment: {
    mild: 0.069,
    moderate: 0.377,
    severe: 0.449,
    source: "GBD 2019 (dementia)",
  },

  // Musculoskeletal
  back_pain: {
    mild: 0.02,
    moderate: 0.054,
    severe: 0.325,
    source: "GBD 2019",
  },
  osteoarthritis: {
    mild: 0.023,
    moderate: 0.079,
    severe: 0.165,
    source: "GBD 2019",
  },
  osteoporosis: {
    mild: 0.0,
    moderate: 0.0,
    severe: 0.0,
    source: "GBD 2019 (via fractures)",
  },

  // Cancer
  cancer: {
    mild: 0.049,
    moderate: 0.288,
    severe: 0.54,
    source: "GBD 2019 (generic)",
  },

  // Sensory
  vision_loss: {
    mild: 0.031,
    moderate: 0.187,
    severe: 0.187,
    source: "GBD 2019",
  },
  hearing_loss: {
    mild: 0.01,
    moderate: 0.027,
    severe: 0.158,
    source: "GBD 2019",
  },

  // Other
  fatigue: {
    mild: 0.03,
    moderate: 0.1,
    severe: 0.2,
    source: "Estimated",
  },
  sleep_disorder: {
    mild: 0.02,
    moderate: 0.1,
    severe: 0.2,
    source: "Estimated from insomnia studies",
  },
  general_wellbeing: {
    mild: 0.0,
    moderate: 0.0,
    severe: 0.0,
    source: "Placeholder for hedonic effects",
  },
};

/**
 * Baseline annual incidence rates per 1000 people by age group
 * These are rough estimates - ideally would be age/sex specific
 */
export const BASELINE_INCIDENCE_PER_1000: Record<
  HealthCondition,
  { age30: number; age50: number; age70: number; source: string }
> = {
  heart_failure: {
    age30: 0.1,
    age50: 1,
    age70: 10,
    source: "Framingham/GBD",
  },
  angina: {
    age30: 0.2,
    age50: 2,
    age70: 8,
    source: "GBD 2019",
  },
  stroke: {
    age30: 0.1,
    age50: 1,
    age70: 10,
    source: "GBD 2019",
  },
  hypertension: {
    age30: 5,
    age50: 20,
    age70: 40,
    source: "NHANES",
  },
  diabetes: {
    age30: 2,
    age50: 8,
    age70: 12,
    source: "CDC",
  },
  obesity: {
    age30: 10,
    age50: 15,
    age70: 10,
    source: "NHANES",
  },
  copd: {
    age30: 0.1,
    age50: 2,
    age70: 8,
    source: "GBD 2019",
  },
  asthma: {
    age30: 3,
    age50: 2,
    age70: 2,
    source: "CDC",
  },
  depression: {
    age30: 30,
    age50: 25,
    age70: 20,
    source: "NIMH",
  },
  anxiety: {
    age30: 35,
    age50: 30,
    age70: 20,
    source: "NIMH",
  },
  cognitive_impairment: {
    age30: 0.01,
    age50: 0.5,
    age70: 20,
    source: "Alzheimer's Association",
  },
  back_pain: {
    age30: 50,
    age50: 60,
    age70: 70,
    source: "GBD 2019",
  },
  osteoarthritis: {
    age30: 2,
    age50: 20,
    age70: 50,
    source: "GBD 2019",
  },
  osteoporosis: {
    age30: 0.1,
    age50: 5,
    age70: 20,
    source: "NOF",
  },
  cancer: {
    age30: 1,
    age50: 5,
    age70: 20,
    source: "SEER",
  },
  vision_loss: {
    age30: 1,
    age50: 5,
    age70: 30,
    source: "NEI",
  },
  hearing_loss: {
    age30: 2,
    age50: 15,
    age70: 50,
    source: "NIDCD",
  },
  fatigue: {
    age30: 50,
    age50: 60,
    age70: 70,
    source: "Estimated",
  },
  sleep_disorder: {
    age30: 30,
    age50: 40,
    age70: 50,
    source: "Sleep Foundation",
  },
  general_wellbeing: {
    age30: 0,
    age50: 0,
    age70: 0,
    source: "N/A",
  },
};

/**
 * Get baseline incidence for a condition at a given age
 */
export function getBaselineIncidence(
  condition: HealthCondition,
  age: number
): number {
  const data = BASELINE_INCIDENCE_PER_1000[condition];

  // Linear interpolation
  if (age <= 30) return data.age30;
  if (age >= 70) return data.age70;

  if (age <= 50) {
    const t = (age - 30) / 20;
    return data.age30 + t * (data.age50 - data.age30);
  } else {
    const t = (age - 50) / 20;
    return data.age50 + t * (data.age70 - data.age50);
  }
}

/**
 * Get disability weight for a condition at a given severity
 */
export function getDisabilityWeight(
  condition: HealthCondition,
  severity: "mild" | "moderate" | "severe" = "moderate"
): number {
  return DISABILITY_WEIGHTS[condition][severity];
}

/**
 * Map which EQ-5D dimensions each condition primarily affects
 */
export const CONDITION_TO_DIMENSIONS: Record<
  HealthCondition,
  { dimension: string; weight: number }[]
> = {
  heart_failure: [
    { dimension: "mobility", weight: 0.4 },
    { dimension: "usualActivities", weight: 0.4 },
    { dimension: "anxietyDepression", weight: 0.2 },
  ],
  angina: [
    { dimension: "painDiscomfort", weight: 0.5 },
    { dimension: "usualActivities", weight: 0.3 },
    { dimension: "anxietyDepression", weight: 0.2 },
  ],
  stroke: [
    { dimension: "mobility", weight: 0.3 },
    { dimension: "selfCare", weight: 0.3 },
    { dimension: "usualActivities", weight: 0.4 },
  ],
  hypertension: [], // Usually asymptomatic
  diabetes: [
    { dimension: "usualActivities", weight: 0.5 },
    { dimension: "anxietyDepression", weight: 0.3 },
    { dimension: "painDiscomfort", weight: 0.2 },
  ],
  obesity: [
    { dimension: "mobility", weight: 0.4 },
    { dimension: "usualActivities", weight: 0.3 },
    { dimension: "anxietyDepression", weight: 0.3 },
  ],
  copd: [
    { dimension: "mobility", weight: 0.4 },
    { dimension: "usualActivities", weight: 0.4 },
    { dimension: "anxietyDepression", weight: 0.2 },
  ],
  asthma: [
    { dimension: "usualActivities", weight: 0.6 },
    { dimension: "anxietyDepression", weight: 0.4 },
  ],
  depression: [
    { dimension: "anxietyDepression", weight: 0.6 },
    { dimension: "usualActivities", weight: 0.3 },
    { dimension: "selfCare", weight: 0.1 },
  ],
  anxiety: [
    { dimension: "anxietyDepression", weight: 0.8 },
    { dimension: "usualActivities", weight: 0.2 },
  ],
  cognitive_impairment: [
    { dimension: "selfCare", weight: 0.4 },
    { dimension: "usualActivities", weight: 0.4 },
    { dimension: "anxietyDepression", weight: 0.2 },
  ],
  back_pain: [
    { dimension: "painDiscomfort", weight: 0.5 },
    { dimension: "mobility", weight: 0.3 },
    { dimension: "usualActivities", weight: 0.2 },
  ],
  osteoarthritis: [
    { dimension: "painDiscomfort", weight: 0.4 },
    { dimension: "mobility", weight: 0.4 },
    { dimension: "usualActivities", weight: 0.2 },
  ],
  osteoporosis: [
    { dimension: "painDiscomfort", weight: 0.4 },
    { dimension: "mobility", weight: 0.4 },
    { dimension: "anxietyDepression", weight: 0.2 },
  ],
  cancer: [
    { dimension: "usualActivities", weight: 0.3 },
    { dimension: "painDiscomfort", weight: 0.3 },
    { dimension: "anxietyDepression", weight: 0.4 },
  ],
  vision_loss: [
    { dimension: "usualActivities", weight: 0.5 },
    { dimension: "mobility", weight: 0.3 },
    { dimension: "selfCare", weight: 0.2 },
  ],
  hearing_loss: [
    { dimension: "usualActivities", weight: 0.6 },
    { dimension: "anxietyDepression", weight: 0.4 },
  ],
  fatigue: [
    { dimension: "usualActivities", weight: 0.6 },
    { dimension: "anxietyDepression", weight: 0.4 },
  ],
  sleep_disorder: [
    { dimension: "usualActivities", weight: 0.4 },
    { dimension: "anxietyDepression", weight: 0.4 },
    { dimension: "painDiscomfort", weight: 0.2 },
  ],
  general_wellbeing: [{ dimension: "anxietyDepression", weight: 1.0 }],
};
