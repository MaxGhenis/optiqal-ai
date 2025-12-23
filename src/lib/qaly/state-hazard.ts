/**
 * State → Hazard Calculator
 *
 * Computes mortality and morbidity hazard rates from PersonState.
 * Connects PersonState (from state.ts) with RISK_FACTORS (from risk-factors.ts).
 */

import type { PersonState } from "./state";
import { getAge } from "./state";
import {
  RISK_FACTORS,
  combineHazardRatios,
  getCauseSpecificHR as getRiskFactorCauseSpecificHR,
  type HRWithUncertainty,
  type HazardValue,
  type PersonState as RiskFactorPersonState,
} from "./risk-factors";
import {
  getAnnualMortalityRate,
  getSurvivalProbability,
  getCauseFraction,
} from "./lifecycle";

/**
 * Result of computing hazards from a PersonState
 */
export interface StateHazardResult {
  // Overall mortality hazard multiplier (product of all risk factors)
  overallHR: number;
  overallHRWithUncertainty: HRWithUncertainty;

  // Cause-specific hazard multipliers
  causeSpecificHR: {
    cvd: number;
    cancer: number;
    other: number;
  };

  // Breakdown by risk factor (for transparency)
  riskFactorContributions: {
    factor: string;
    hr: number;
    contribution: number; // % of total log-HR
  }[];

  // Quality-of-life decrement from conditions
  qualityDecrement: number;
}

/**
 * Helper to extract point estimate from HazardValue
 */
function getPoint(hr: HazardValue): number {
  return typeof hr === "number" ? hr : hr.point;
}

/**
 * Helper to convert PersonState to RiskFactorPersonState
 */
function convertToRiskFactorState(state: PersonState): RiskFactorPersonState {
  const age = getAge(state);

  // Map smoking status
  let smokingStatus: RiskFactorPersonState["smokingStatus"] = "never";
  if (state.behaviors.smoking.status === "current") {
    const cigarettesPerDay = state.behaviors.smoking.cigarettesPerDay || 10;
    if (cigarettesPerDay <= 10) {
      smokingStatus = "current_1_10";
    } else if (cigarettesPerDay <= 20) {
      smokingStatus = "current_11_20";
    } else {
      smokingStatus = "current_21_plus";
    }
  } else if (state.behaviors.smoking.status === "former") {
    const yearsQuit = state.behaviors.smoking.yearsQuit || 0;
    if (yearsQuit < 5) {
      smokingStatus = "former_0_5_years";
    } else if (yearsQuit < 10) {
      smokingStatus = "former_5_10_years";
    } else if (yearsQuit < 15) {
      smokingStatus = "former_10_15_years";
    } else {
      smokingStatus = "former_15_plus_years";
    }
  }

  // Map social connections
  let socialConnection: "strong" | "moderate" | "weak" | "isolated" = "moderate";
  if (state.behaviors.social.closeRelationships >= 5) {
    socialConnection = "strong";
  } else if (state.behaviors.social.closeRelationships >= 3) {
    socialConnection = "moderate";
  } else if (state.behaviors.social.closeRelationships >= 1) {
    socialConnection = "weak";
  } else {
    socialConnection = "isolated";
  }

  // Convert diet to mediterranean score (0-9 scale)
  // Mediterranean diet score based on adherence (0-1) scaled to 0-9
  const mediterraneanDietScore = state.behaviors.diet.mediterraneanAdherence * 9;

  // Estimate processed meat from diet
  const processedMeatGramsPerDay =
    (state.behaviors.diet.redMeatServingsPerWeek * 100) / 7; // Rough estimate

  // Estimate fruits/vegetables
  const fruitsVegetablesGramsPerDay =
    (state.behaviors.diet.vegetableServingsPerDay +
      state.behaviors.diet.fruitServingsPerDay) *
    80; // ~80g per serving

  return {
    age,
    sex: state.demographics.sex,
    smokingStatus,
    bmi: state.biomarkers.bmi || 25, // Default to healthy BMI if missing
    exerciseMinutesPerWeek: state.behaviors.exercise.aerobicMinutesPerWeek,
    alcoholDrinksPerWeek: state.behaviors.alcohol.drinksPerWeek,
    sleepHoursPerNight: state.behaviors.sleep.hoursPerNight,
    systolicBP: state.biomarkers.systolicBP || 120, // Default to normal if missing
    mediterraneanDietScore,
    processedMeatGramsPerDay,
    fruitsVegetablesGramsPerDay,
    socialConnection,
  };
}

/**
 * Compute hazard rates from PersonState
 */
export function computeStateHazards(state: PersonState): StateHazardResult {
  const riskFactorState = convertToRiskFactorState(state);
  const age = getAge(state);

  // Get all risk factor HRs
  const smokingHR = RISK_FACTORS.smoking.getHazardRatio(
    riskFactorState.smokingStatus
  );
  const bmiHR = RISK_FACTORS.bmi.getHazardRatio(riskFactorState.bmi);
  const exerciseHR = RISK_FACTORS.exercise.getHazardRatio(
    riskFactorState.exerciseMinutesPerWeek
  );
  const alcoholHR = RISK_FACTORS.alcohol.getHazardRatio(
    riskFactorState.alcoholDrinksPerWeek
  );
  const sleepHR = RISK_FACTORS.sleep.getHazardRatio(
    riskFactorState.sleepHoursPerNight
  );
  const bloodPressureHR = RISK_FACTORS.bloodPressure.getHazardRatio(
    riskFactorState.systolicBP,
    { age, sex: state.demographics.sex }
  );
  const mediterraneanDietHR = RISK_FACTORS.mediterraneanDiet.getHazardRatio(
    riskFactorState.mediterraneanDietScore
  );
  const processedMeatHR = RISK_FACTORS.processedMeat.getHazardRatio(
    riskFactorState.processedMeatGramsPerDay
  );
  const fruitsVegetablesHR = RISK_FACTORS.fruitsVegetables.getHazardRatio(
    riskFactorState.fruitsVegetablesGramsPerDay
  );
  const socialHR = RISK_FACTORS.socialConnection.getHazardRatio(
    riskFactorState.socialConnection
  );

  // Extract point estimates
  const hrs = {
    smoking: getPoint(smokingHR),
    bmi: getPoint(bmiHR),
    exercise: getPoint(exerciseHR),
    alcohol: getPoint(alcoholHR),
    sleep: getPoint(sleepHR),
    bloodPressure: getPoint(bloodPressureHR),
    mediterraneanDiet: getPoint(mediterraneanDietHR),
    processedMeat: getPoint(processedMeatHR),
    fruitsVegetables: getPoint(fruitsVegetablesHR),
    social: getPoint(socialHR),
  };

  // Combine multiplicatively
  const overallHR = combineHazardRatios(Object.values(hrs));

  // Calculate contributions (% of total log-HR)
  const totalLogHR = Math.log(overallHR);
  const contributions = Object.entries(hrs).map(([factor, hr]) => {
    const logHR = Math.log(Math.max(0.01, hr)); // Ensure positive
    const contribution = totalLogHR !== 0 ? (logHR / totalLogHR) * 100 : 0;
    return {
      factor,
      hr,
      contribution,
    };
  });

  // Create uncertainty estimate for overall HR
  // Combine uncertainties on log scale
  const logHRs = [
    smokingHR,
    bmiHR,
    exerciseHR,
    alcoholHR,
    sleepHR,
    bloodPressureHR,
    mediterraneanDietHR,
    processedMeatHR,
    fruitsVegetablesHR,
    socialHR,
  ].map((hr) => {
    if (typeof hr === "number") {
      return { logHR: Math.log(hr), logSd: 0.05 }; // Assume small uncertainty
    } else {
      return { logHR: Math.log(hr.point), logSd: hr.logSd };
    }
  });

  const sumLogHR = logHRs.reduce((sum, x) => sum + x.logHR, 0);
  const sumVariance = logHRs.reduce((sum, x) => sum + x.logSd * x.logSd, 0);
  const combinedLogSd = Math.sqrt(sumVariance);

  const overallHRWithUncertainty: HRWithUncertainty = {
    point: overallHR,
    ci95Lower: Math.exp(sumLogHR - 1.96 * combinedLogSd),
    ci95Upper: Math.exp(sumLogHR + 1.96 * combinedLogSd),
    logSd: combinedLogSd,
  };

  // Compute cause-specific HRs using risk-factors.ts logic
  const cvdHR = getRiskFactorCauseSpecificHR(riskFactorState, "cvd");
  const cancerHR = getRiskFactorCauseSpecificHR(riskFactorState, "cancer");
  const otherHR = getRiskFactorCauseSpecificHR(riskFactorState, "other");

  // Compute quality decrement from conditions
  const qualityDecrement = computeQualityDecrement(state);

  return {
    overallHR,
    overallHRWithUncertainty,
    causeSpecificHR: {
      cvd: cvdHR,
      cancer: cancerHR,
      other: otherHR,
    },
    riskFactorContributions: contributions.sort(
      (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)
    ),
    qualityDecrement,
  };
}

/**
 * Compute quality-of-life decrement from conditions
 */
function computeQualityDecrement(state: PersonState): number {
  // Simple model: each condition contributes a decrement
  // Source: GBD 2019 disability weights
  const conditionWeights: Record<string, number> = {
    diabetes: 0.05,
    hypertension: 0.02,
    "heart-disease": 0.15,
    stroke: 0.30,
    cancer: 0.25,
    copd: 0.20,
    depression: 0.15,
    anxiety: 0.10,
  };

  let totalDecrement = 0;
  for (const condition of state.conditions) {
    const weight = conditionWeights[condition.type] || 0.05; // Default small weight
    const severityMultiplier =
      condition.severity === "severe"
        ? 1.5
        : condition.severity === "moderate"
          ? 1.0
          : 0.5;
    totalDecrement += weight * severityMultiplier;
  }

  // Cap at 0.8 (20% minimum quality of life)
  return Math.min(0.8, totalDecrement);
}

/**
 * Compute state hazards with Monte Carlo uncertainty propagation
 */
export function computeStateHazardsWithUncertainty(
  state: PersonState,
  nSamples: number = 1000
): StateHazardResult & { samples: number[] } {
  const baseResult = computeStateHazards(state);
  const samples: number[] = [];

  // Sample from log-normal distribution
  const logMean = Math.log(baseResult.overallHR);
  const logSd = baseResult.overallHRWithUncertainty.logSd;

  for (let i = 0; i < nSamples; i++) {
    // Box-Muller transform for normal samples
    const u1 = Math.random();
    const u2 = Math.random();
    const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    const logSample = logMean + z * logSd;
    samples.push(Math.exp(logSample));
  }

  return {
    ...baseResult,
    samples,
  };
}

/**
 * Get life expectancy from state
 */
export function getLifeExpectancy(
  state: PersonState
): { expected: number; ci95: { low: number; high: number } } {
  const age = getAge(state);
  const sex = state.demographics.sex;
  const hazards = computeStateHazards(state);

  // Integrate survival probability over remaining lifetime
  let lifeExpectancy = 0;
  let survivalProb = 1.0;

  for (let yearOffset = 0; yearOffset < 100 - age; yearOffset++) {
    const currentAge = age + yearOffset;
    const baselineMortality = getAnnualMortalityRate(currentAge, sex);
    const adjustedMortality = baselineMortality * hazards.overallHR;

    // Add expected survival for this year
    lifeExpectancy += survivalProb;

    // Update survival probability
    survivalProb *= 1 - Math.min(0.99, adjustedMortality); // Cap at 99% to avoid negative

    // Stop if survival is negligible
    if (survivalProb < 0.001) break;
  }

  // Compute confidence interval using HR uncertainty
  const lowerHR = hazards.overallHRWithUncertainty.ci95Lower;
  const upperHR = hazards.overallHRWithUncertainty.ci95Upper;

  // Lower HR → higher life expectancy
  let lowerLE = 0;
  let upperLE = 0;
  let survivalLower = 1.0;
  let survivalUpper = 1.0;

  for (let yearOffset = 0; yearOffset < 100 - age; yearOffset++) {
    const currentAge = age + yearOffset;
    const baselineMortality = getAnnualMortalityRate(currentAge, sex);

    upperLE += survivalLower;
    survivalLower *= 1 - Math.min(0.99, baselineMortality * lowerHR);

    lowerLE += survivalUpper;
    survivalUpper *= 1 - Math.min(0.99, baselineMortality * upperHR);

    if (survivalLower < 0.001 && survivalUpper < 0.001) break;
  }

  return {
    expected: lifeExpectancy,
    ci95: {
      low: lowerLE,
      high: upperLE,
    },
  };
}

/**
 * Get annual mortality probability at given age
 */
export function getAnnualMortalityFromState(
  state: PersonState,
  age: number
): number {
  const sex = state.demographics.sex;
  const hazards = computeStateHazards(state);

  const baselineMortality = getAnnualMortalityRate(age, sex);
  const adjustedMortality = baselineMortality * hazards.overallHR;

  // Cap at 99% (can't exceed certain death)
  return Math.min(0.99, adjustedMortality);
}
