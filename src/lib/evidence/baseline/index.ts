/**
 * Baseline QALY Calculator
 *
 * Calculates expected remaining QALYs for a user profile
 * based on life tables and quality weights.
 */

import {
  getRemainingLifeExpectancy,
  getLifeExpectancy,
} from "./life-tables";
import {
  getAgeQualityWeight,
  getQualityWeightWithConditions,
} from "./quality-weights";
import type { UserProfile } from "@/types";

export interface BaselineProjection {
  remainingLifeExpectancy: number; // years
  expectedDeathAge: number;
  currentQualityWeight: number;
  remainingQALYs: number;
  breakdown: {
    ageDecade: number;
    yearsInDecade: number;
    avgQualityWeight: number;
    qalysInDecade: number;
  }[];
  /** Year-by-year survival and QALY data for charts */
  survivalCurve: {
    age: number;
    survivalProbability: number; // 0-1, probability of being alive at this age
    qualityWeight: number; // 0-1, expected quality of life
    expectedQALY: number; // survivalProbability * qualityWeight
  }[];
}

/**
 * Risk factor adjustments to life expectancy
 * Based on GBD 2019 comparative risk assessment
 *
 * These are multiplicative factors on mortality rate
 * HR > 1 means increased mortality (shorter life)
 * HR < 1 means decreased mortality (longer life)
 */
const RISK_FACTOR_HAZARD_RATIOS = {
  // Smoking: Meta-analysis of 141 cohort studies (Thun et al., NEJM 2013)
  smoking: {
    current: { hr: 2.8, source: "Thun et al., NEJM 2013" },
    former: { hr: 1.3, source: "Thun et al., NEJM 2013" }, // 10+ years quit
  },

  // BMI: Global BMI Mortality Collaboration, Lancet 2016
  bmi: {
    underweight: { hr: 1.51, source: "BMI <18.5, Global BMI Mortality Collab" },
    normal: { hr: 1.0, source: "BMI 18.5-25, reference" },
    overweight: { hr: 1.11, source: "BMI 25-30, Global BMI Mortality Collab" },
    obese1: { hr: 1.44, source: "BMI 30-35, Global BMI Mortality Collab" },
    obese2: { hr: 1.92, source: "BMI 35-40, Global BMI Mortality Collab" },
    obese3: { hr: 2.76, source: "BMI 40+, Global BMI Mortality Collab" },
  },

  // Exercise: Arem et al., JAMA Internal Medicine 2015
  // Comparing to recommended 7.5 MET-hours/week (~2.5 hrs moderate exercise)
  exercise: {
    none: { hr: 1.31, source: "0 hrs/week, Arem et al. JAMA Int Med 2015" },
    low: { hr: 1.14, source: "<2.5 hrs/week, Arem et al." },
    recommended: { hr: 1.0, source: "2.5-5 hrs/week, reference" },
    high: { hr: 0.94, source: "5-7.5 hrs/week, Arem et al." },
    veryHigh: { hr: 0.96, source: "7.5+ hrs/week, Arem et al." }, // slight U-curve
  },

  // Sleep: Cappuccio et al., Sleep 2010 meta-analysis
  sleep: {
    short: { hr: 1.12, source: "<6 hrs/night, Cappuccio et al. Sleep 2010" },
    normal: { hr: 1.0, source: "6-9 hrs/night, reference" },
    long: { hr: 1.3, source: ">9 hrs/night, Cappuccio et al. Sleep 2010" },
  },
};

/**
 * Calculate BMI category
 */
function getBMICategory(
  weight: number,
  height: number
): keyof typeof RISK_FACTOR_HAZARD_RATIOS.bmi {
  const heightM = height / 100;
  const bmi = weight / (heightM * heightM);

  if (bmi < 18.5) return "underweight";
  if (bmi < 25) return "normal";
  if (bmi < 30) return "overweight";
  if (bmi < 35) return "obese1";
  if (bmi < 40) return "obese2";
  return "obese3";
}

/**
 * Get exercise category
 */
function getExerciseCategory(
  hoursPerWeek: number
): keyof typeof RISK_FACTOR_HAZARD_RATIOS.exercise {
  if (hoursPerWeek === 0) return "none";
  if (hoursPerWeek < 2.5) return "low";
  if (hoursPerWeek < 5) return "recommended";
  if (hoursPerWeek < 7.5) return "high";
  return "veryHigh";
}

/**
 * Get sleep category
 */
function getSleepCategory(
  hoursPerNight: number
): keyof typeof RISK_FACTOR_HAZARD_RATIOS.sleep {
  if (hoursPerNight < 6) return "short";
  if (hoursPerNight <= 9) return "normal";
  return "long";
}

/**
 * Convert hazard ratio to life expectancy adjustment
 * Simplified: HR of 2 roughly halves remaining life expectancy
 * More accurate would use full actuarial calculations
 */
function hrToLifeExpectancyMultiplier(hr: number): number {
  // Using ln(HR) approximation for proportional hazards
  // This is simplified but reasonable for moderate HRs
  return 1 / Math.pow(hr, 0.5);
}

/**
 * Calculate baseline QALY projection for a user profile
 */
export function calculateBaselineQALYs(profile: UserProfile): BaselineProjection {
  const { age, sex, weight, height, smoker, exerciseHoursPerWeek, sleepHoursPerNight } =
    profile;

  // Start with population average life expectancy
  let remainingLE = getRemainingLifeExpectancy(age, sex);

  // Apply risk factor adjustments
  const bmiCategory = getBMICategory(weight, height);
  const exerciseCategory = getExerciseCategory(exerciseHoursPerWeek);
  const sleepCategory = getSleepCategory(sleepHoursPerNight);

  const hrBMI = RISK_FACTOR_HAZARD_RATIOS.bmi[bmiCategory].hr;
  const hrExercise = RISK_FACTOR_HAZARD_RATIOS.exercise[exerciseCategory].hr;
  const hrSleep = RISK_FACTOR_HAZARD_RATIOS.sleep[sleepCategory].hr;
  const hrSmoking = smoker
    ? RISK_FACTOR_HAZARD_RATIOS.smoking.current.hr
    : 1.0;

  // Combined HR (multiplicative)
  const combinedHR = hrBMI * hrExercise * hrSleep * hrSmoking;

  // Adjust life expectancy
  remainingLE *= hrToLifeExpectancyMultiplier(combinedHR);

  const expectedDeathAge = age + remainingLE;

  // Calculate QALYs decade by decade
  const breakdown: BaselineProjection["breakdown"] = [];
  let totalQALYs = 0;
  let currentAge = age;

  while (currentAge < expectedDeathAge) {
    const decadeStart = Math.floor(currentAge / 10) * 10;
    const decadeEnd = Math.min(decadeStart + 10, expectedDeathAge);
    const yearsInDecade = Math.min(decadeEnd - currentAge, expectedDeathAge - currentAge);

    if (yearsInDecade <= 0) break;

    // Average quality weight for this period
    const midpointAge = currentAge + yearsInDecade / 2;
    const avgQualityWeight = getAgeQualityWeight(midpointAge);

    const qalysInDecade = yearsInDecade * avgQualityWeight;
    totalQALYs += qalysInDecade;

    breakdown.push({
      ageDecade: decadeStart,
      yearsInDecade,
      avgQualityWeight,
      qalysInDecade,
    });

    currentAge = decadeEnd;
  }

  // Generate survival curve data for visualization
  // Using simplified Gompertz-like survival model
  const survivalCurve: BaselineProjection["survivalCurve"] = [];
  const maxAge = 100;

  for (let chartAge = age; chartAge <= maxAge; chartAge += 5) {
    // Survival probability decreases as we approach expected death age
    // Using a sigmoid-like decay centered around expected death
    const yearsFromNow = chartAge - age;
    const yearsToExpectedDeath = expectedDeathAge - age;

    // Gompertz-inspired survival: S(t) = exp(-exp(a + b*t))
    // Simplified: probability drops steeply around expected death age
    let survivalProbability: number;
    if (chartAge <= age) {
      survivalProbability = 1.0;
    } else if (chartAge >= expectedDeathAge + 15) {
      survivalProbability = 0.01;
    } else {
      // Logistic decay centered at expected death age
      const k = 0.15; // steepness
      const midpoint = expectedDeathAge;
      survivalProbability = 1 / (1 + Math.exp(k * (chartAge - midpoint)));
    }

    const qualityWeight = getAgeQualityWeight(chartAge);
    const expectedQALY = survivalProbability * qualityWeight;

    survivalCurve.push({
      age: chartAge,
      survivalProbability: Math.max(0, Math.min(1, survivalProbability)),
      qualityWeight,
      expectedQALY: Math.max(0, Math.min(1, expectedQALY)),
    });
  }

  return {
    remainingLifeExpectancy: remainingLE,
    expectedDeathAge,
    currentQualityWeight: getAgeQualityWeight(age),
    remainingQALYs: totalQALYs,
    breakdown,
    survivalCurve,
  };
}

// Re-export for convenience
export { getRemainingLifeExpectancy, getLifeExpectancy } from "./life-tables";
export {
  getAgeQualityWeight,
  getQualityWeightWithConditions,
  CONDITION_DISABILITY_WEIGHTS,
} from "./quality-weights";
export {
  loadPrecomputedBaselines,
  getPrecomputedLifeExpectancy,
  getPrecomputedRemainingQALYs,
  getPrecomputedCauseFractions,
  getPrecomputedQualityWeight,
  type PrecomputedBaselines,
} from "./precomputed";

// Partial profile and uncertainty quantification
export {
  type PartialProfile,
  sampleCompleteProfile,
  calculateProfileCompleteness,
  getMissingFields,
  partialToMeanProfile,
} from "./partial-profile";
export {
  calculateBaselineWithUncertainty,
  calculateBaselineQuick,
  formatPredictionInterval,
  type UncertainBaselineResult,
} from "./uncertain-baseline";
