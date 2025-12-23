/**
 * Counterfactual simulation with imputation-based causal inference
 *
 * KEY INNOVATION: Separating causal effects from confounding
 *
 * The problem:
 * - Naive comparison: Compare person with behavior X to typical person with behavior Y
 * - Issue: People who do Y also have other healthy behaviors (confounding)
 * - Result: Overestimation of causal effect
 *
 * Our solution:
 * 1. Impute full baseline state from limited observations
 * 2. Apply intervention (change one behavior)
 * 3. Propagate through CAUSAL pathways only (not correlational)
 * 4. Keep non-causal correlates FIXED at baseline values
 * 5. Compute QALY difference (causal effect)
 *
 * Example:
 * - Baseline: Obese person (BMI 32) with poor diet (imputed)
 * - Intervention: Add exercise (150 min/week)
 * - Counterfactual: Same person + exercise + BMI reduction (causal)
 * - Naive comparison: Typical exerciser (also has good diet, BMI 24)
 * - Causal effect < Naive effect (confounding absorbed)
 *
 * This gives more realistic causal estimates.
 */

import type { PersonState, Behaviors } from "./state";
import { updateState, getAge } from "./state";
import { compareStates, identifyStateChanges } from "./state-diff";
import {
  imputeFullState,
  createTypicalStateWithBehavior,
  deepCopy,
  CAUSAL_DAG,
  type PartialObservation,
} from "./imputation";

/**
 * Map simple CAUSAL_DAG names to full PersonState paths
 */
const DOWNSTREAM_PATH_MAP: Record<string, string> = {
  // Biomarkers
  bmi: "biomarkers.bmi",
  systolicBP: "biomarkers.systolicBP",
  diastolicBP: "biomarkers.diastolicBP",
  hdlCholesterol: "biomarkers.hdlCholesterol",
  ldlCholesterol: "biomarkers.ldlCholesterol",
  totalCholesterol: "biomarkers.totalCholesterol",
  triglycerides: "biomarkers.triglycerides",
  fastingGlucose: "biomarkers.fastingGlucose",
  hba1c: "biomarkers.hba1c",
  crp: "biomarkers.crp",
  egfr: "biomarkers.egfr",
  restingHR: "biomarkers.restingHR",

  // Behaviors
  sleepHours: "behaviors.sleep.hoursPerNight",

  // Mental health (map to stress level - simplified)
  depression: "behaviors.stress.chronicStressLevel",

  // Lung function - not directly in state, store on biomarkers
  lungFunction: "biomarkers.egfr", // Placeholder - could add lungFunction to biomarkers
};

/**
 * Result of a counterfactual simulation
 */
export interface CounterfactualResult {
  // The causal QALY effect (isolated from confounding)
  causalEffect: {
    mean: number;
    ci95: { low: number; high: number };
  };

  // For comparison: what naive state comparison would give
  naiveEffect: {
    mean: number;
    ci95: { low: number; high: number };
  };

  // The difference (confounding absorbed)
  confoundingAbsorbed: number;

  // States for transparency
  baselineState: PersonState;
  counterfactualState: PersonState;
  naiveComparisonState: PersonState; // what we'd compare to naively

  // What changed through causal pathways
  causalChanges: {
    variable: string;
    before: number;
    after: number;
    source: string;
  }[];

  // What was held fixed (would have changed in naive comparison)
  heldFixed: {
    variable: string;
    value: number;
    wouldHaveBeen: number; // in naive comparison
  }[];
}

/**
 * Intervention specification
 */
export interface Intervention {
  variable: "exercise" | "diet" | "smoking" | "alcohol" | "sleep";
  change: Partial<Behaviors>;
}

/**
 * Simulation options
 */
export interface CounterfactualOptions {
  nSimulations?: number;
  propagateCausalEffects?: boolean; // default true
}

/**
 * Simulate the causal effect of an intervention
 *
 * @param observed - What we know about the person
 * @param intervention - What behavior to change
 * @param options - Simulation options
 */
export function simulateCausalIntervention(
  observed: PartialObservation,
  intervention: Intervention,
  options?: CounterfactualOptions
): CounterfactualResult {
  const { nSimulations = 1000, propagateCausalEffects = true } = options || {};

  // 1. Impute full baseline state from observed
  const baseline = imputeFullState(observed);

  // 2. Create counterfactual state
  const counterfactual = deepCopy(baseline.state);

  // 3. Apply the intervention
  applyIntervention(counterfactual, intervention);

  // 4. Propagate through CAUSAL pathways only
  const causalChanges: CounterfactualResult["causalChanges"] = [];

  if (propagateCausalEffects) {
    const effects = CAUSAL_DAG[intervention.variable] || [];
    for (const effect of effects) {
      const change = propagateCausalEffect(
        counterfactual,
        baseline.state,
        effect,
        intervention
      );
      if (change) {
        causalChanges.push(change);
      }
    }
  }

  // 5. Keep non-causal correlates FIXED at baseline values
  // (This is automatic - we only changed intervention + downstream)

  // 6. Create naive comparison state (typical person with target behavior)
  const naiveTarget = createTypicalStateWithBehavior(
    {
      variable: intervention.variable,
      value: intervention.change,
    },
    observed.age,
    observed.sex
  );

  // 7. Compute QALY difference (causal effect)
  const causalQALY = compareStates(baseline.state, counterfactual, {
    nSimulations,
  });

  // 8. Compute naive effect
  const naiveQALY = compareStates(baseline.state, naiveTarget, {
    nSimulations,
  });

  // 9. Identify what was held fixed
  const heldFixed = identifyHeldFixed(
    baseline.state,
    counterfactual,
    naiveTarget
  );

  // Add intervention change to causalChanges
  const interventionChanges = getInterventionChanges(
    baseline.state,
    counterfactual,
    intervention
  );
  causalChanges.unshift(...interventionChanges);

  return {
    causalEffect: causalQALY.qalyDifference,
    naiveEffect: naiveQALY.qalyDifference,
    confoundingAbsorbed:
      naiveQALY.qalyDifference.mean - causalQALY.qalyDifference.mean,
    baselineState: baseline.state,
    counterfactualState: counterfactual,
    naiveComparisonState: naiveTarget,
    causalChanges,
    heldFixed,
  };
}

/**
 * Apply intervention to state
 */
function applyIntervention(
  state: PersonState,
  intervention: Intervention
): void {
  if (intervention.variable === "exercise" && intervention.change.exercise) {
    Object.assign(state.behaviors.exercise, intervention.change.exercise);
  } else if (intervention.variable === "diet" && intervention.change.diet) {
    Object.assign(state.behaviors.diet, intervention.change.diet);
  } else if (
    intervention.variable === "smoking" &&
    intervention.change.smoking
  ) {
    Object.assign(state.behaviors.smoking, intervention.change.smoking);
  } else if (
    intervention.variable === "alcohol" &&
    intervention.change.alcohol
  ) {
    Object.assign(state.behaviors.alcohol, intervention.change.alcohol);
  } else if (intervention.variable === "sleep" && intervention.change.sleep) {
    Object.assign(state.behaviors.sleep, intervention.change.sleep);
  }
}

/**
 * Propagate causal downstream effect
 */
function propagateCausalEffect(
  state: PersonState,
  baseline: PersonState,
  effect: { downstream: string; effectSize: number },
  intervention: Intervention
): { variable: string; before: number; after: number; source: string } | null {
  // Calculate the magnitude of the intervention
  const interventionMagnitude = getInterventionMagnitude(
    baseline,
    intervention
  );

  // Scale the effect
  const scaledEffect = effect.effectSize * interventionMagnitude;

  // Map simple name to full path
  const fullPath = DOWNSTREAM_PATH_MAP[effect.downstream] || effect.downstream;

  // Apply to downstream variable
  const parts = fullPath.split(".");
  let current: any = state;
  let beforeCurrent: any = baseline;

  // Navigate to the target (all but last part)
  for (let i = 0; i < parts.length - 1; i++) {
    if (current[parts[i]] === undefined) {
      return null; // Path doesn't exist
    }
    current = current[parts[i]];
    beforeCurrent = beforeCurrent[parts[i]];
  }

  const finalKey = parts[parts.length - 1];
  const before = beforeCurrent[finalKey] ?? 0;
  const after = (current[finalKey] ?? 0) + scaledEffect;

  current[finalKey] = after;

  return {
    variable: fullPath,
    before,
    after,
    source: `causal from ${intervention.variable}`,
  };
}

/**
 * Calculate the magnitude of intervention (for scaling effects)
 */
function getInterventionMagnitude(
  baseline: PersonState,
  intervention: Intervention
): number {
  if (intervention.variable === "exercise" && intervention.change.exercise) {
    const baselineMinutes =
      baseline.behaviors.exercise.aerobicMinutesPerWeek || 0;
    const targetMinutes =
      intervention.change.exercise.aerobicMinutesPerWeek || 0;
    // Normalize to 150 min/week as unit (1.0)
    return (targetMinutes - baselineMinutes) / 150;
  } else if (intervention.variable === "diet" && intervention.change.diet) {
    const baselineAdherence =
      baseline.behaviors.diet.mediterraneanAdherence || 0;
    const targetAdherence =
      intervention.change.diet.mediterraneanAdherence ?? baselineAdherence;
    // Scale 0-1 adherence as magnitude
    return targetAdherence - baselineAdherence;
  } else if (
    intervention.variable === "smoking" &&
    intervention.change.smoking
  ) {
    // Binary: quitting = magnitude 1.0
    if (
      baseline.behaviors.smoking.status !== "never" &&
      intervention.change.smoking.status === "never"
    ) {
      return 1.0;
    }
    return 0;
  }

  return 1.0; // default
}

/**
 * Identify what was held fixed vs what changed in naive comparison
 */
function identifyHeldFixed(
  baseline: PersonState,
  counterfactual: PersonState,
  naive: PersonState
): CounterfactualResult["heldFixed"] {
  const heldFixed: CounterfactualResult["heldFixed"] = [];

  // Check behaviors.diet
  if (
    baseline.behaviors.diet.mediterraneanAdherence ===
      counterfactual.behaviors.diet.mediterraneanAdherence &&
    baseline.behaviors.diet.mediterraneanAdherence !==
      naive.behaviors.diet.mediterraneanAdherence
  ) {
    heldFixed.push({
      variable: "behaviors.diet.mediterraneanAdherence",
      value: baseline.behaviors.diet.mediterraneanAdherence,
      wouldHaveBeen: naive.behaviors.diet.mediterraneanAdherence,
    });
  }

  // Check behaviors.exercise
  if (
    baseline.behaviors.exercise.aerobicMinutesPerWeek ===
      counterfactual.behaviors.exercise.aerobicMinutesPerWeek &&
    baseline.behaviors.exercise.aerobicMinutesPerWeek !==
      naive.behaviors.exercise.aerobicMinutesPerWeek
  ) {
    heldFixed.push({
      variable: "behaviors.exercise.aerobicMinutesPerWeek",
      value: baseline.behaviors.exercise.aerobicMinutesPerWeek,
      wouldHaveBeen: naive.behaviors.exercise.aerobicMinutesPerWeek,
    });
  }

  // Check behaviors.smoking
  if (
    baseline.behaviors.smoking.status ===
      counterfactual.behaviors.smoking.status &&
    baseline.behaviors.smoking.status !== naive.behaviors.smoking.status
  ) {
    heldFixed.push({
      variable: "behaviors.smoking.status",
      value: baseline.behaviors.smoking.status === "never" ? 0 : 1,
      wouldHaveBeen: naive.behaviors.smoking.status === "never" ? 0 : 1,
    });
  }

  // Check biomarkers.bmi
  if (
    Math.abs(
      (baseline.biomarkers.bmi || 0) - (counterfactual.biomarkers.bmi || 0)
    ) < 0.1 &&
    Math.abs((baseline.biomarkers.bmi || 0) - (naive.biomarkers.bmi || 0)) > 1
  ) {
    // Only count as "held fixed" if causal propagation didn't change it much
    // but naive comparison has very different BMI
    // (BMI might change slightly due to causal effects, but that's intended)
  }

  return heldFixed;
}

/**
 * Get changes from the intervention itself
 */
function getInterventionChanges(
  baseline: PersonState,
  counterfactual: PersonState,
  intervention: Intervention
): CounterfactualResult["causalChanges"] {
  const changes: CounterfactualResult["causalChanges"] = [];

  if (intervention.variable === "exercise" && intervention.change.exercise) {
    if (intervention.change.exercise.aerobicMinutesPerWeek !== undefined) {
      changes.push({
        variable: "behaviors.exercise.aerobicMinutesPerWeek",
        before: baseline.behaviors.exercise.aerobicMinutesPerWeek,
        after: counterfactual.behaviors.exercise.aerobicMinutesPerWeek,
        source: "intervention",
      });
    }
  } else if (intervention.variable === "diet" && intervention.change.diet) {
    if (intervention.change.diet.mediterraneanAdherence !== undefined) {
      changes.push({
        variable: "behaviors.diet.mediterraneanAdherence",
        before: baseline.behaviors.diet.mediterraneanAdherence,
        after: counterfactual.behaviors.diet.mediterraneanAdherence,
        source: "intervention",
      });
    }
    if (intervention.change.diet.vegetableServingsPerDay !== undefined) {
      changes.push({
        variable: "behaviors.diet.vegetableServingsPerDay",
        before: baseline.behaviors.diet.vegetableServingsPerDay,
        after: counterfactual.behaviors.diet.vegetableServingsPerDay,
        source: "intervention",
      });
    }
  } else if (
    intervention.variable === "smoking" &&
    intervention.change.smoking
  ) {
    changes.push({
      variable: "behaviors.smoking.status",
      before: baseline.behaviors.smoking.status === "never" ? 0 : 1,
      after: counterfactual.behaviors.smoking.status === "never" ? 0 : 1,
      source: "intervention",
    });
  }

  return changes;
}
