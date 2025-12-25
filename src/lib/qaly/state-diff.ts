/**
 * State Diff for Intervention Comparison
 *
 * Key insight: An "intervention" is just the difference between two states.
 * - State A: current state
 * - State B: state after behavior change
 * - QALY impact = E[QALY | State_B] - E[QALY | State_A]
 *
 * This module compares PersonStates and computes QALY impact.
 *
 * Example usage:
 *
 * ```typescript
 * import { createDefaultState, computeInterventionImpact, compareInterventions } from './qaly';
 *
 * // Create baseline state
 * const myState = createDefaultState(40, "male");
 *
 * // Compare single intervention
 * const exerciseImpact = computeInterventionImpact(myState, {
 *   behaviors: {
 *     exercise: {
 *       aerobicMinutesPerWeek: 300  // Increase from 150 to 300
 *     }
 *   }
 * });
 *
 * console.log(`Expected QALY gain: ${exerciseImpact.qalyDifference.mean.toFixed(2)}`);
 * console.log(`95% CI: [${exerciseImpact.qalyDifference.ci95.low.toFixed(2)}, ${exerciseImpact.qalyDifference.ci95.high.toFixed(2)}]`);
 *
 * // Compare multiple interventions
 * const results = compareInterventions(myState, {
 *   "exercise_300min": { behaviors: { exercise: { aerobicMinutesPerWeek: 300 } } },
 *   "quit_smoking": { behaviors: { smoking: { status: "never" } } },
 *   "mediterranean_diet": { behaviors: { diet: { mediterraneanAdherence: 0.8 } } }
 * });
 *
 * // Rank by impact
 * const ranked = Object.entries(results)
 *   .sort((a, b) => b[1].qalyDifference.mean - a[1].qalyDifference.mean)
 *   .map(([name, result]) => ({
 *     intervention: name,
 *     qalys: result.qalyDifference.mean,
 *     lifeYears: result.lifeExpectancyDifference.mean
 *   }));
 * ```
 */

import type { PersonState, DeepPartial } from "./state";
import { updateState, getAge } from "./state";
import { random, setSeed } from "./random";
import { calculateLifecycleQALYs, type PathwayHRs } from "./lifecycle";
import { RISK_FACTORS } from "./risk-factors";

/**
 * State comparison result with QALY impact
 */
export interface StateComparisonResult {
  // Core result
  qalyDifference: {
    mean: number;
    median: number;
    ci95: { low: number; high: number };
  };

  // Component breakdown
  breakdown: {
    mortalityQALYs: number; // From living longer
    qualityQALYs: number; // From better quality while alive
  };

  // Life expectancy change
  lifeExpectancyDifference: {
    mean: number;
    ci95: { low: number; high: number };
  };

  // What changed
  changedFactors: {
    factor: string;
    before: unknown;
    after: unknown;
    hazardRatioChange: number;
  }[];

  // Probability metrics
  probPositive: number; // P(QALY gain > 0)
  probMoreThanOneYear: number; // P(QALY gain > 1)

  // Trajectory comparison
  trajectoryComparison: {
    year: number;
    age: number;
    survivalA: number;
    survivalB: number;
    qalyA: number;
    qalyB: number;
  }[];
}

/**
 * Simulation options
 */
export interface SimulationOptions {
  nSimulations?: number;
  discountRate?: number;
  seed?: number | string;
}

/**
 * Map PersonState to a simplified state for risk factor calculation
 */
function stateToRiskFactorState(state: PersonState): {
  age: number;
  sex: "male" | "female";
  smokingStatus: string;
  bmi: number;
  exerciseMinutesPerWeek: number;
  alcoholDrinksPerWeek: number;
  sleepHoursPerNight: number;
  systolicBP: number;
  mediterraneanDietScore: number;
  processedMeatGramsPerDay: number;
  fruitsVegetablesGramsPerDay: number;
  socialConnection: "strong" | "moderate" | "weak" | "isolated";
} {
  const age = getAge(state);

  // Map smoking status to risk factor categories
  let smokingStatus: string = state.behaviors.smoking.status;
  if (state.behaviors.smoking.status === "current") {
    const cpd = state.behaviors.smoking.cigarettesPerDay || 10;
    if (cpd <= 10) smokingStatus = "current_1_10";
    else if (cpd <= 20) smokingStatus = "current_11_20";
    else smokingStatus = "current_21_plus";
  } else if (state.behaviors.smoking.status === "former") {
    const yearsQuit = state.behaviors.smoking.yearsQuit || 0;
    if (yearsQuit < 5) smokingStatus = "former_0_5_years";
    else if (yearsQuit < 10) smokingStatus = "former_5_10_years";
    else if (yearsQuit < 15) smokingStatus = "former_10_15_years";
    else smokingStatus = "former_15_plus_years";
  }

  // Map social connection from state
  const closeRel = state.behaviors.social.closeRelationships;
  const hours = state.behaviors.social.weeklyInteractionHours;
  let socialConnection: "strong" | "moderate" | "weak" | "isolated";
  if (closeRel >= 5 && hours >= 10) socialConnection = "strong";
  else if (closeRel >= 3 && hours >= 5) socialConnection = "moderate";
  else if (closeRel >= 1) socialConnection = "weak";
  else socialConnection = "isolated";

  // Convert diet metrics
  const mediterraneanDietScore = state.behaviors.diet.mediterraneanAdherence * 9; // 0-1 -> 0-9
  const processedMeatGramsPerDay = state.behaviors.diet.redMeatServingsPerWeek * 50 / 7; // rough conversion
  const fruitsVegetablesGramsPerDay =
    (state.behaviors.diet.vegetableServingsPerDay + state.behaviors.diet.fruitServingsPerDay) *
    80; // 1 serving ~ 80g

  return {
    age,
    sex: state.demographics.sex,
    smokingStatus,
    bmi: state.biomarkers.bmi || 25,
    exerciseMinutesPerWeek: state.behaviors.exercise.aerobicMinutesPerWeek,
    alcoholDrinksPerWeek: state.behaviors.alcohol.drinksPerWeek,
    sleepHoursPerNight: state.behaviors.sleep.hoursPerNight,
    systolicBP: state.biomarkers.systolicBP || 120,
    mediterraneanDietScore,
    processedMeatGramsPerDay,
    fruitsVegetablesGramsPerDay,
    socialConnection,
  };
}

/**
 * Calculate combined hazard ratio from a state
 */
function getHazardRatioFromState(
  state: PersonState,
  sampleUncertainty: boolean = false
): number {
  const riskState = stateToRiskFactorState(state);

  const smoking = sampleUncertainty
    ? sampleHR(RISK_FACTORS.smoking.getHazardRatio(riskState.smokingStatus))
    : getPoint(RISK_FACTORS.smoking.getHazardRatio(riskState.smokingStatus));

  const bmi = sampleUncertainty
    ? sampleHR(RISK_FACTORS.bmi.getHazardRatio(riskState.bmi))
    : getPoint(RISK_FACTORS.bmi.getHazardRatio(riskState.bmi));

  const exercise = sampleUncertainty
    ? sampleHR(RISK_FACTORS.exercise.getHazardRatio(riskState.exerciseMinutesPerWeek))
    : getPoint(
        RISK_FACTORS.exercise.getHazardRatio(riskState.exerciseMinutesPerWeek)
      );

  const alcohol = sampleUncertainty
    ? sampleHR(RISK_FACTORS.alcohol.getHazardRatio(riskState.alcoholDrinksPerWeek))
    : getPoint(RISK_FACTORS.alcohol.getHazardRatio(riskState.alcoholDrinksPerWeek));

  const sleep = sampleUncertainty
    ? sampleHR(RISK_FACTORS.sleep.getHazardRatio(riskState.sleepHoursPerNight))
    : getPoint(RISK_FACTORS.sleep.getHazardRatio(riskState.sleepHoursPerNight));

  const bloodPressure = sampleUncertainty
    ? sampleHR(
        RISK_FACTORS.bloodPressure.getHazardRatio(riskState.systolicBP, {
          age: riskState.age,
          sex: riskState.sex,
        })
      )
    : getPoint(
        RISK_FACTORS.bloodPressure.getHazardRatio(riskState.systolicBP, {
          age: riskState.age,
          sex: riskState.sex,
        })
      );

  const mediterraneanDiet = sampleUncertainty
    ? sampleHR(
        RISK_FACTORS.mediterraneanDiet.getHazardRatio(riskState.mediterraneanDietScore)
      )
    : getPoint(
        RISK_FACTORS.mediterraneanDiet.getHazardRatio(riskState.mediterraneanDietScore)
      );

  const processedMeat = sampleUncertainty
    ? sampleHR(
        RISK_FACTORS.processedMeat.getHazardRatio(riskState.processedMeatGramsPerDay)
      )
    : getPoint(
        RISK_FACTORS.processedMeat.getHazardRatio(riskState.processedMeatGramsPerDay)
      );

  const fruitsVegetables = sampleUncertainty
    ? sampleHR(
        RISK_FACTORS.fruitsVegetables.getHazardRatio(
          riskState.fruitsVegetablesGramsPerDay
        )
      )
    : getPoint(
        RISK_FACTORS.fruitsVegetables.getHazardRatio(
          riskState.fruitsVegetablesGramsPerDay
        )
      );

  const social = sampleUncertainty
    ? sampleHR(RISK_FACTORS.socialConnection.getHazardRatio(riskState.socialConnection))
    : getPoint(
        RISK_FACTORS.socialConnection.getHazardRatio(riskState.socialConnection)
      );

  // Combine multiplicatively
  return (
    smoking *
    bmi *
    exercise *
    alcohol *
    sleep *
    bloodPressure *
    mediterraneanDiet *
    processedMeat *
    fruitsVegetables *
    social
  );
}

/**
 * Helper to extract point estimate from HazardValue
 */
function getPoint(hr: number | { point: number }): number {
  return typeof hr === "number" ? hr : hr.point;
}

/**
 * Sample from hazard ratio uncertainty distribution
 */
function sampleHR(hr: number | { point: number; logSd: number }): number {
  if (typeof hr === "number") return hr;

  // Sample from log-normal distribution
  const logHR = Math.log(hr.point);
  const sampledLogHR = logHR + hr.logSd * randomNormal();
  return Math.exp(sampledLogHR);
}

/**
 * Sample from standard normal distribution (Box-Muller transform)
 */
function randomNormal(): number {
  const u1 = random();
  const u2 = random();
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

/**
 * Identify what changed between two states
 */
export function identifyStateChanges(
  stateA: PersonState,
  stateB: PersonState
): { path: string; before: unknown; after: unknown }[] {
  const changes: { path: string; before: unknown; after: unknown }[] = [];

  // Helper to recursively compare objects
  function compareObjects(
    a: any,
    b: any,
    path: string = ""
  ): void {
    if (typeof a !== "object" || typeof b !== "object" || a === null || b === null) {
      if (a !== b) {
        changes.push({ path, before: a, after: b });
      }
      return;
    }

    // Handle arrays
    if (Array.isArray(a) && Array.isArray(b)) {
      // For now, just check if arrays are different
      if (JSON.stringify(a) !== JSON.stringify(b)) {
        changes.push({ path, before: a, after: b });
      }
      return;
    }

    // Compare object keys
    const allKeys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const key of allKeys) {
      const newPath = path ? `${path}.${key}` : key;

      if (!(key in a)) {
        changes.push({ path: newPath, before: undefined, after: b[key] });
      } else if (!(key in b)) {
        changes.push({ path: newPath, before: a[key], after: undefined });
      } else {
        compareObjects(a[key], b[key], newPath);
      }
    }
  }

  compareObjects(stateA, stateB);
  return changes;
}

/**
 * Convert overall HR to pathway HRs
 * Simplified version - assumes equal distribution
 */
function hrToPathwayHRs(hr: number): PathwayHRs {
  // For simplicity, apply HR equally to all pathways
  // In reality, different risk factors affect different pathways differently
  return {
    cvd: hr,
    cancer: hr,
    other: hr,
  };
}

/**
 * Compare two states and compute QALY impact
 */
export function compareStates(
  stateA: PersonState,
  stateB: PersonState,
  options: SimulationOptions = {}
): StateComparisonResult {
  const { nSimulations = 1000, discountRate = 0.03, seed = 42 } = options;

  // Set seed for reproducibility
  setSeed(seed);

  const age = getAge(stateA);
  const sex = stateA.demographics.sex;

  // Run Monte Carlo simulations
  const qalyDifferences: number[] = [];
  const lifeExpectancyDifferences: number[] = [];

  // First check if states are identical
  const statesIdentical = JSON.stringify(stateA) === JSON.stringify(stateB);

  if (statesIdentical) {
    // If states are identical, no need to simulate - difference is exactly 0
    for (let i = 0; i < nSimulations; i++) {
      qalyDifferences.push(0);
      lifeExpectancyDifferences.push(0);
    }
  } else {
    for (let i = 0; i < nSimulations; i++) {
      // Sample hazard ratios with uncertainty for each simulation
      // Always use uncertainty sampling for proper CI estimation
      const hrA = getHazardRatioFromState(stateA, true);
      const hrB = getHazardRatioFromState(stateB, true);

      // Convert to pathway HRs
      const pathwayHRsA = hrToPathwayHRs(hrA);
      const pathwayHRsB = hrToPathwayHRs(hrB);

      const resultA = calculateLifecycleQALYs({
        startAge: age,
        sex,
        pathwayHRs: pathwayHRsA,
        discountRate,
      });

      const resultB = calculateLifecycleQALYs({
        startAge: age,
        sex,
        pathwayHRs: pathwayHRsB,
        discountRate,
      });

      // Use interventionQALYs to compare the two states
      // Each result has baselineQALYs (no intervention) and interventionQALYs (with intervention)
      qalyDifferences.push(resultB.interventionQALYs - resultA.interventionQALYs);
      lifeExpectancyDifferences.push(resultB.lifeYearsGained - resultA.lifeYearsGained);
    }
  }

  // Calculate statistics
  const mean = qalyDifferences.reduce((sum, v) => sum + v, 0) / nSimulations;
  const sorted = [...qalyDifferences].sort((a, b) => a - b);
  const median = sorted[Math.floor(nSimulations / 2)];
  const ci95Low = sorted[Math.floor(nSimulations * 0.025)];
  const ci95High = sorted[Math.floor(nSimulations * 0.975)];

  const leMean =
    lifeExpectancyDifferences.reduce((sum, v) => sum + v, 0) / nSimulations;
  const leSorted = [...lifeExpectancyDifferences].sort((a, b) => a - b);
  const leCi95Low = leSorted[Math.floor(nSimulations * 0.025)];
  const leCi95High = leSorted[Math.floor(nSimulations * 0.975)];

  // Calculate probabilities
  const probPositive = qalyDifferences.filter((v) => v > 0).length / nSimulations;
  const probMoreThanOneYear =
    qalyDifferences.filter((v) => v > 1).length / nSimulations;

  // Get trajectory comparison (use point estimates, not sampled)
  const hrAPoint = getHazardRatioFromState(stateA, false);
  const hrBPoint = getHazardRatioFromState(stateB, false);

  const resultA = calculateLifecycleQALYs({
    startAge: age,
    sex,
    pathwayHRs: hrToPathwayHRs(hrAPoint),
    discountRate,
  });

  const resultB = calculateLifecycleQALYs({
    startAge: age,
    sex,
    pathwayHRs: hrToPathwayHRs(hrBPoint),
    discountRate,
  });

  const trajectoryComparison = resultA.yearlyBreakdown.map((yearA, i) => {
    const yearB = resultB.yearlyBreakdown[i];
    return {
      year: yearA.year,
      age: yearA.age,
      survivalA: yearA.survivalBaseline,
      survivalB: yearB.survivalIntervention,
      qalyA: yearA.qalyBaseline,
      qalyB: yearB.qalyIntervention,
    };
  });

  // Identify changed factors with hazard ratio changes
  const changes = identifyStateChanges(stateA, stateB);
  const changedFactors = changes.map((change) => {
    // Calculate hazard ratio change for this specific factor
    // This is a simplified version - we compare overall HRs
    return {
      factor: change.path,
      before: change.before,
      after: change.after,
      hazardRatioChange: hrBPoint / hrAPoint, // Simplified
    };
  });

  // Breakdown mortality vs quality QALYs
  // Simplified: assume all QALY difference is from mortality
  // In reality, would need to track quality-adjusted life years separately
  const mortalityQALYs = mean;
  const qualityQALYs = 0;

  return {
    qalyDifference: {
      mean,
      median,
      ci95: { low: ci95Low, high: ci95High },
    },
    breakdown: {
      mortalityQALYs,
      qualityQALYs,
    },
    lifeExpectancyDifference: {
      mean: leMean,
      ci95: { low: leCi95Low, high: leCi95High },
    },
    changedFactors,
    probPositive,
    probMoreThanOneYear,
    trajectoryComparison,
  };
}

/**
 * Apply a single behavior change and compute impact
 */
export function computeInterventionImpact(
  baseState: PersonState,
  intervention: DeepPartial<PersonState>,
  options?: SimulationOptions
): StateComparisonResult {
  const newState = updateState(baseState, intervention);
  return compareStates(baseState, newState, options);
}

/**
 * Compare multiple interventions against baseline
 */
export function compareInterventions(
  baseState: PersonState,
  interventions: Record<string, DeepPartial<PersonState>>,
  options?: SimulationOptions
): Record<string, StateComparisonResult> {
  const results: Record<string, StateComparisonResult> = {};

  for (const [name, intervention] of Object.entries(interventions)) {
    results[name] = computeInterventionImpact(baseState, intervention, options);
  }

  return results;
}
