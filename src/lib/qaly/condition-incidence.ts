/**
 * Condition Incidence Models
 *
 * This module extends the causal DAG to include:
 * 1. Condition incidence models: Risk factors → P(condition)
 * 2. Quality decrements: Condition → utility loss
 * 3. Integration with lifecycle QALY calculation
 *
 * Key insight: Age-related quality decline is mostly explained by
 * accumulated conditions. We model conditions directly rather than
 * using age-based population norms (which would double-count).
 *
 * Data sources:
 * - Framingham Risk Score for CVD
 * - UKPDS for diabetes complications
 * - UK Biobank for incidence rates
 * - NICE DSU for quality decrements
 */

import type { PersonState } from "./state";
import { getAge } from "./state";

// =============================================================================
// CONDITION DEFINITIONS
// =============================================================================

/**
 * Conditions that affect quality of life
 * Each has incidence risk models and quality decrements
 */
export type Condition =
  | "type2_diabetes"
  | "coronary_heart_disease"
  | "stroke"
  | "heart_failure"
  | "hypertension" // Stage 2+
  | "obesity_class2" // BMI ≥ 35
  | "copd"
  | "depression"
  | "arthritis"
  | "chronic_kidney_disease";

// =============================================================================
// QUALITY DECREMENTS BY CONDITION
// =============================================================================

/**
 * Quality utility decrements by condition
 *
 * Sources:
 * - UKPDS 62 (Clarke 2002): Diabetes complications
 * - Sullivan & Ghushchyan 2006: US EQ-5D catalog
 * - NICE DSU TSD 12: Health state utilities
 *
 * These are MARGINAL decrements (effect of having condition vs not)
 * after controlling for age, sex, and comorbidities
 */
export const CONDITION_DECREMENTS: Record<
  Condition,
  {
    decrement: number; // Utility loss (negative)
    se: number; // Standard error
    source: string;
  }
> = {
  type2_diabetes: {
    decrement: -0.06,
    se: 0.01,
    source: "UKPDS 62 baseline diabetes effect",
  },
  coronary_heart_disease: {
    decrement: -0.09,
    se: 0.02,
    source: "UKPDS 62: IHD/MI effect = -0.090",
  },
  stroke: {
    decrement: -0.16,
    se: 0.03,
    source: "UKPDS 62: Stroke effect = -0.164",
  },
  heart_failure: {
    decrement: -0.12,
    se: 0.02,
    source: "Sullivan catalog: CHF",
  },
  hypertension: {
    decrement: -0.02,
    se: 0.01,
    source: "Sullivan catalog: controlled HTN is minor",
  },
  obesity_class2: {
    decrement: -0.05,
    se: 0.01,
    source: "UKPDS 62: BMI 35+ vs 25 = -0.05",
  },
  copd: {
    decrement: -0.08,
    se: 0.02,
    source: "Sullivan catalog: moderate COPD",
  },
  depression: {
    decrement: -0.10,
    se: 0.02,
    source: "Sullivan catalog: major depression",
  },
  arthritis: {
    decrement: -0.08,
    se: 0.02,
    source: "Sullivan catalog: osteoarthritis",
  },
  chronic_kidney_disease: {
    decrement: -0.07,
    se: 0.02,
    source: "UKPDS 62: nephropathy",
  },
};

// =============================================================================
// PURE AGING EFFECT (residual after conditions)
// =============================================================================

/**
 * Pure aging quality decrement
 *
 * This is the residual age effect AFTER controlling for conditions.
 * Reflects frailty, sensory decline, cognitive slowing not captured by
 * specific diagnoses.
 *
 * Estimate: ~0.002/year after age 50, based on:
 * - EQ-5D norms showing ~0.01/decade decline in healthy elderly
 * - Most of that explained by conditions
 * - Residual is modest
 */
export function pureAgingDecrement(age: number): number {
  if (age <= 50) return 0;
  // 0.002 per year = 0.02 per decade = 0.06 at age 80
  return (age - 50) * 0.002;
}

/**
 * Healthy baseline utility (no conditions, young adult)
 * This is the ceiling - actual utility decreases from here
 */
export const HEALTHY_BASELINE = 0.95;

// =============================================================================
// CONDITION INCIDENCE MODELS
// =============================================================================

/**
 * Risk factor inputs for condition incidence
 */
export interface RiskFactors {
  age: number;
  sex: "male" | "female";
  bmi: number;
  systolicBP: number;
  totalCholesterol?: number;
  hdlCholesterol?: number;
  ldlCholesterol?: number;
  hba1c?: number; // % for diabetes risk
  smokingStatus: "never" | "former" | "current";
  smokingPackYears?: number;
  diabetesStatus: boolean;
  exerciseMinPerWeek: number;
  familyHistoryCVD?: boolean;
}

/**
 * Extract risk factors from PersonState
 */
export function extractRiskFactors(state: PersonState): RiskFactors {
  // Check if person has diabetes diagnosis in conditions array
  // HealthCondition type uses "diabetes" not "type2_diabetes"
  const hasDiabetes = state.conditions.some((c) => c.type === "diabetes");

  return {
    age: getAge(state),
    sex: state.demographics.sex,
    bmi: state.biomarkers.bmi ?? 25,
    systolicBP: state.biomarkers.systolicBP ?? 120,
    totalCholesterol: state.biomarkers.totalCholesterol,
    hdlCholesterol: state.biomarkers.hdlCholesterol,
    ldlCholesterol: state.biomarkers.ldlCholesterol,
    hba1c: state.biomarkers.hba1c,
    smokingStatus: state.behaviors.smoking.status,
    smokingPackYears: state.behaviors.smoking.packYears,
    diabetesStatus: hasDiabetes,
    exerciseMinPerWeek: state.behaviors.exercise.aerobicMinutesPerWeek,
    familyHistoryCVD: undefined, // Not tracked in current PersonState
  };
}

/**
 * Annual incidence probability for type 2 diabetes
 *
 * Based on: Finnish Diabetes Risk Score (FINDRISC) + US calibration
 * Key predictors: age, BMI, waist, BP, family history, physical activity
 *
 * Simplified model using available data
 */
export function diabetesIncidence(rf: RiskFactors): number {
  // Base annual incidence by age (per 1000)
  // Source: CDC National Diabetes Statistics Report 2022
  const baseRateByAge: Record<string, number> = {
    "18-44": 4.0, // 0.4%
    "45-64": 12.5, // 1.25%
    "65+": 10.2, // 1.02%
  };

  const ageGroup =
    rf.age < 45 ? "18-44" : rf.age < 65 ? "45-64" : "65+";
  let baseRate = baseRateByAge[ageGroup] / 1000;

  // BMI adjustment (relative risk)
  // Source: Guh 2009 meta-analysis
  // RR per 5 kg/m² increase ≈ 1.87 for men, 1.84 for women
  const bmiRR = Math.pow(rf.sex === "male" ? 1.87 : 1.84, (rf.bmi - 25) / 5);

  // Physical activity adjustment
  // Source: Aune 2015 meta-analysis
  // 150 min/week = 26% risk reduction
  const exerciseRR =
    rf.exerciseMinPerWeek >= 150
      ? 0.74
      : rf.exerciseMinPerWeek >= 75
        ? 0.87
        : 1.0;

  // Hypertension adjustment
  // Source: Wei 1999
  // HTN RR ≈ 1.5 for diabetes
  const htRR = rf.systolicBP >= 140 ? 1.5 : rf.systolicBP >= 130 ? 1.2 : 1.0;

  return Math.min(baseRate * bmiRR * exerciseRR * htRR, 0.1); // Cap at 10%/year
}

/**
 * 10-year CVD risk (CHD + stroke)
 *
 * Based on: Pooled Cohort Equations (ACC/AHA 2013)
 * Simplified for available risk factors
 */
export function cvdRisk10Year(rf: RiskFactors): number {
  // Framingham-style calculation
  // Source: D'Agostino 2008 general cardiovascular risk
  const sexMultiplier = rf.sex === "male" ? 1.0 : 0.8;

  // Age risk (roughly doubles per decade after 40)
  const ageRisk = rf.age < 40 ? 0.01 : Math.pow(1.08, rf.age - 40) * 0.02;

  // Cholesterol risk (if available)
  const cholRatio = rf.hdlCholesterol
    ? (rf.totalCholesterol ?? 200) / rf.hdlCholesterol
    : 4.5; // Default ratio
  const cholRR = Math.pow(1.2, (cholRatio - 4) / 2);

  // Blood pressure risk
  // Lewington 2002: 20 mmHg SBP = 2x CVD risk
  const bpRR = Math.pow(2, (rf.systolicBP - 120) / 20);

  // Smoking risk
  const smokeRR =
    rf.smokingStatus === "current"
      ? 2.0
      : rf.smokingStatus === "former"
        ? 1.3
        : 1.0;

  // Diabetes risk
  const diabetesRR = rf.diabetesStatus ? 2.5 : 1.0;

  // Physical activity (inverse)
  const exerciseRR =
    rf.exerciseMinPerWeek >= 150
      ? 0.75
      : rf.exerciseMinPerWeek >= 75
        ? 0.85
        : 1.0;

  // Combine (multiplicative on relative scale)
  const risk10yr =
    ageRisk * sexMultiplier * cholRR * bpRR * smokeRR * diabetesRR * exerciseRR;

  return Math.min(risk10yr, 0.5); // Cap at 50%
}

/**
 * Annual CVD incidence (from 10-year risk)
 */
export function cvdIncidenceAnnual(rf: RiskFactors): number {
  const risk10yr = cvdRisk10Year(rf);
  // Convert to annual: 1 - (1-p)^(1/10)
  return 1 - Math.pow(1 - risk10yr, 0.1);
}

/**
 * Stroke incidence (subset of CVD)
 * Roughly 20-30% of CVD events are strokes
 */
export function strokeIncidenceAnnual(rf: RiskFactors): number {
  return cvdIncidenceAnnual(rf) * 0.25;
}

/**
 * CHD incidence (subset of CVD)
 * Roughly 50-60% of CVD events are CHD
 */
export function chdIncidenceAnnual(rf: RiskFactors): number {
  return cvdIncidenceAnnual(rf) * 0.55;
}

/**
 * Depression incidence
 *
 * Based on: NHANES + meta-analyses
 * Key predictors: age, sex, exercise, sleep, social connection
 */
export function depressionIncidenceAnnual(rf: RiskFactors): number {
  // Base annual incidence ~3% for adults
  // Source: NIMH, varies by demographics
  let baseRate = rf.sex === "female" ? 0.04 : 0.025;

  // Age adjustment (U-shaped)
  if (rf.age < 30) baseRate *= 1.2;
  else if (rf.age > 65) baseRate *= 0.7; // Lower in elderly

  // Exercise is protective
  // Schuch 2016: OR ≈ 0.83 for physically active
  const exerciseRR = rf.exerciseMinPerWeek >= 150 ? 0.75 : 1.0;

  // Obesity associated with depression
  const bmiRR = rf.bmi >= 30 ? 1.3 : 1.0;

  return baseRate * exerciseRR * bmiRR;
}

// =============================================================================
// CONDITION PREVALENCE MODELS (cumulative incidence)
// =============================================================================

/**
 * Estimate current condition probability based on risk factors and age
 *
 * This approximates "has this person likely developed condition X by now?"
 * Uses cumulative incidence from a hypothetical start age
 */
export function conditionPrevalence(
  condition: Condition,
  rf: RiskFactors
): number {
  // Simplified: assume risk factors have been constant
  // Integrate incidence over time from age 30 to current age
  const startAge = 30;
  if (rf.age <= startAge) return 0;

  let cumulativeRisk = 0;
  for (let age = startAge; age < rf.age; age++) {
    const rfAtAge = { ...rf, age };
    let annualInc: number;

    switch (condition) {
      case "type2_diabetes":
        annualInc = diabetesIncidence(rfAtAge);
        break;
      case "coronary_heart_disease":
        annualInc = chdIncidenceAnnual(rfAtAge);
        break;
      case "stroke":
        annualInc = strokeIncidenceAnnual(rfAtAge);
        break;
      case "depression":
        annualInc = depressionIncidenceAnnual(rfAtAge);
        break;
      case "hypertension":
        // Prevalence model: ~35% by age 45, ~65% by age 65
        annualInc = rf.systolicBP >= 140 ? 0.05 : 0.02;
        break;
      case "obesity_class2":
        // Direct from BMI - not really incidence
        return rf.bmi >= 35 ? 1.0 : 0.0;
      default:
        annualInc = 0.01; // Default low incidence
    }

    // Cumulative: P(ever) = 1 - product of (1 - annual)
    cumulativeRisk = cumulativeRisk + (1 - cumulativeRisk) * annualInc;
  }

  return Math.min(cumulativeRisk, 0.9); // Cap at 90%
}

// =============================================================================
// QUALITY CALCULATION
// =============================================================================

/**
 * Calculate current quality of life utility
 *
 * Uses condition-based approach:
 * 1. Start from healthy baseline (0.95)
 * 2. Subtract condition decrements weighted by probability
 * 3. Subtract small pure-aging effect
 */
export function calculateQuality(state: PersonState): number {
  const rf = extractRiskFactors(state);
  let utility = HEALTHY_BASELINE;

  // Subtract expected quality loss from each condition
  for (const [condition, data] of Object.entries(CONDITION_DECREMENTS)) {
    const prevalence = conditionPrevalence(condition as Condition, rf);
    utility += data.decrement * prevalence; // decrement is negative
  }

  // Subtract pure aging effect
  utility -= pureAgingDecrement(rf.age);

  // Floor at 0 (dead)
  return Math.max(0, utility);
}

/**
 * Calculate quality gain from intervention
 *
 * Intervention reduces condition risk → fewer quality decrements
 */
export function interventionQualityEffect(
  baseState: PersonState,
  interventionState: PersonState,
  yearsRemaining: number
): number {
  const baseRf = extractRiskFactors(baseState);
  const intRf = extractRiskFactors(interventionState);

  let qualityGain = 0;

  // For each condition, calculate expected quality saved
  for (const [condition, data] of Object.entries(CONDITION_DECREMENTS)) {
    const cond = condition as Condition;

    // Calculate annual incidence difference
    let baseIncidence: number;
    let intIncidence: number;

    switch (cond) {
      case "type2_diabetes":
        baseIncidence = diabetesIncidence(baseRf);
        intIncidence = diabetesIncidence(intRf);
        break;
      case "coronary_heart_disease":
        baseIncidence = chdIncidenceAnnual(baseRf);
        intIncidence = chdIncidenceAnnual(intRf);
        break;
      case "stroke":
        baseIncidence = strokeIncidenceAnnual(baseRf);
        intIncidence = strokeIncidenceAnnual(intRf);
        break;
      case "depression":
        baseIncidence = depressionIncidenceAnnual(baseRf);
        intIncidence = depressionIncidenceAnnual(intRf);
        break;
      default:
        continue; // Skip conditions without incidence models
    }

    // Risk reduction
    const incidenceReduction = baseIncidence - intIncidence;
    if (incidenceReduction <= 0) continue;

    // Expected years with condition avoided
    // Simplified: incidence reduction * years * avg years with condition
    const avgYearsWithCondition = yearsRemaining / 2;
    const qualitySaved =
      incidenceReduction *
      avgYearsWithCondition *
      Math.abs(data.decrement);

    qualityGain += qualitySaved;
  }

  return qualityGain;
}

// =============================================================================
// INTEGRATION WITH EXISTING DAG
// =============================================================================

/**
 * Extended causal pathway:
 *
 * Intervention (exercise, diet, etc.)
 *     ↓
 * Biomarkers (BMI, BP, cholesterol) [existing CAUSAL_DAG]
 *     ↓
 * Condition Risk (diabetes, CVD, stroke) [NEW: incidence models]
 *     ↓
 * Quality of Life [NEW: condition decrements]
 *     ↓
 * QALYs [existing lifecycle integration]
 *
 * The key change: instead of applying hazard ratios directly to mortality,
 * we now also track how biomarker changes affect condition incidence,
 * which affects quality of life throughout remaining years.
 */

export interface QualityImpact {
  condition: Condition;
  baselineIncidence: number;
  interventionIncidence: number;
  incidenceReduction: number;
  qualityDecrement: number;
  expectedQualitySaved: number;
}

/**
 * Detailed breakdown of quality impacts by condition
 */
export function detailedQualityImpact(
  baseState: PersonState,
  interventionState: PersonState,
  yearsRemaining: number
): QualityImpact[] {
  const baseRf = extractRiskFactors(baseState);
  const intRf = extractRiskFactors(interventionState);
  const impacts: QualityImpact[] = [];

  const conditionsWithModels: Condition[] = [
    "type2_diabetes",
    "coronary_heart_disease",
    "stroke",
    "depression",
  ];

  for (const condition of conditionsWithModels) {
    let baseInc: number;
    let intInc: number;

    switch (condition) {
      case "type2_diabetes":
        baseInc = diabetesIncidence(baseRf);
        intInc = diabetesIncidence(intRf);
        break;
      case "coronary_heart_disease":
        baseInc = chdIncidenceAnnual(baseRf);
        intInc = chdIncidenceAnnual(intRf);
        break;
      case "stroke":
        baseInc = strokeIncidenceAnnual(baseRf);
        intInc = strokeIncidenceAnnual(intRf);
        break;
      case "depression":
        baseInc = depressionIncidenceAnnual(baseRf);
        intInc = depressionIncidenceAnnual(intRf);
        break;
      default:
        continue;
    }

    const decrement = CONDITION_DECREMENTS[condition].decrement;
    const incReduction = baseInc - intInc;
    const avgYearsWithCondition = yearsRemaining / 2;
    const qualitySaved =
      incReduction * avgYearsWithCondition * Math.abs(decrement);

    impacts.push({
      condition,
      baselineIncidence: baseInc,
      interventionIncidence: intInc,
      incidenceReduction: incReduction,
      qualityDecrement: decrement,
      expectedQualitySaved: qualitySaved,
    });
  }

  return impacts.filter((i) => i.incidenceReduction > 0);
}
