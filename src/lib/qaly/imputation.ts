/**
 * Behavior Imputation and Causal DAG
 *
 * This module provides:
 * 1. Imputation of behaviors from limited demographic/clinical data
 * 2. A causal DAG defining which interventions affect which downstream variables
 *
 * Key insight: Exercise and diet are CORRELATED but don't CAUSE each other.
 * When we intervene on exercise, we only change exercise and its causal descendants
 * (BMI, BP, etc), NOT diet. This isolates the causal effect.
 *
 * Data sources:
 * - NHANES 2017-2020 for population statistics
 * - UK Biobank for correlation structures
 * - RCTs for causal effect sizes (DPP, PREDIMED, etc)
 */

import type { PersonState, Behaviors } from "./state";
import { createDefaultState } from "./state";

/**
 * Causal effect of an intervention on a downstream variable
 */
export interface CausalEffect {
  downstream: string;
  effectSize: number; // units depend on variable
  perUnit: string; // what the effect size is per
  source: string; // citation/justification
}

/**
 * Causal DAG: which interventions causally affect which downstream variables
 *
 * Key insight: Exercise and diet are CORRELATED but exercise doesn't CAUSE diet changes.
 * When we intervene on exercise, diet stays fixed.
 *
 * Sources: RCTs showing causal effects
 */
export const CAUSAL_DAG: Record<string, CausalEffect[]> = {
  // Exercise causally affects:
  exercise: [
    {
      downstream: "bmi",
      effectSize: -0.5,
      perUnit: "per 150 min/week",
      source: "DPP trial - lifestyle intervention",
    },
    {
      downstream: "systolicBP",
      effectSize: -4,
      perUnit: "per 150 min/week",
      source: "Cornelissen 2013 meta-analysis",
    },
    {
      downstream: "hdlCholesterol",
      effectSize: 3,
      perUnit: "per 150 min/week",
      source: "Kodama 2007 meta-analysis",
    },
    {
      downstream: "sleepHours",
      effectSize: 0.2,
      perUnit: "per 150 min/week",
      source: "Kredlow 2015 meta-analysis",
    },
    {
      downstream: "depression",
      effectSize: -0.3,
      perUnit: "SD per 150 min/week",
      source: "Schuch 2016 meta-analysis",
    },
  ],

  // Diet causally affects:
  diet: [
    {
      downstream: "bmi",
      effectSize: -1.0,
      perUnit: "per 0.5 Mediterranean adherence",
      source: "PREDIMED trial",
    },
    {
      downstream: "ldlCholesterol",
      effectSize: -10,
      perUnit: "per 0.5 Mediterranean adherence",
      source: "PREDIMED trial",
    },
    {
      downstream: "systolicBP",
      effectSize: -3,
      perUnit: "per 0.5 adherence",
      source: "DASH trial",
    },
  ],

  // Smoking cessation causally affects:
  smoking_cessation: [
    {
      downstream: "bmi",
      effectSize: 2.0,
      perUnit: "average gain after quitting",
      source: "Aubin 2012 meta-analysis",
    },
    {
      downstream: "systolicBP",
      effectSize: -5,
      perUnit: "after cessation",
      source: "Oncken 2001",
    },
    {
      downstream: "lungFunction",
      effectSize: 5,
      perUnit: "% FEV1 improvement",
      source: "Scanlon 2000 Lung Health Study",
    },
  ],

  // Alcohol reduction causally affects:
  alcohol_reduction: [
    {
      downstream: "bmi",
      effectSize: -0.3,
      perUnit: "per 7 drinks/week reduction",
      source: "Traversy 2015 review",
    },
    {
      downstream: "systolicBP",
      effectSize: -3,
      perUnit: "per 50% reduction",
      source: "Roerecke 2017 meta-analysis",
    },
  ],

  // Sleep improvement causally affects:
  sleep: [
    {
      downstream: "bmi",
      effectSize: -0.2,
      perUnit: "per 1 hour more sleep",
      source: "Cappuccio 2008",
    },
    {
      downstream: "depression",
      effectSize: -0.2,
      perUnit: "SD per 1 hour improvement",
      source: "Baglioni 2011",
    },
  ],
};

/**
 * Partial observation input for imputation
 */
export interface PartialObservation {
  age: number;
  sex: "male" | "female";
  bmi?: number;
  smokingStatus?: "never" | "former" | "current";
  education?: "high_school" | "some_college" | "college" | "graduate";
}

// Alias for backward compatibility
export type ImputationInput = PartialObservation;

/**
 * Result of imputation
 */
export interface ImputationResult {
  state: PersonState;
  imputedFields: string[]; // Simple field names: "exercise", "diet", "bmi", etc.
  confidence: Record<string, number>; // 0-1 confidence score per field
  // Keep these for backward compatibility
  imputedVariables: string[];
  uncertainty: Record<string, number>;
}

/**
 * Imputed behaviors with uncertainty
 */
export interface ImputedBehaviors {
  exercise: {
    aerobicMinutesPerWeek: number;
    sd: number;
  };
  diet: {
    mediterraneanAdherence: number;
    sd: number;
  };
  alcohol: {
    drinksPerWeek: number;
    sd: number;
  };
  sleep: {
    hoursPerNight: number;
    sd: number;
  };
  social: {
    closeRelationships: number;
    sd: number;
  };
}

/**
 * Get causal effects for an intervention type
 */
export function getCausalEffects(intervention: string): CausalEffect[] {
  return CAUSAL_DAG[intervention] || [];
}

/**
 * Check if variable B is causally downstream of intervention A
 */
export function isCausallyDownstream(
  intervention: string,
  variable: string
): boolean {
  const effects = CAUSAL_DAG[intervention] || [];
  return effects.some((e) => e.downstream === variable);
}

/**
 * Impute behaviors from demographic/clinical data
 *
 * Uses NHANES-like population statistics to predict likely behaviors
 * given observed characteristics.
 */
export function imputeBehaviors(input: ImputationInput): ImputedBehaviors {
  const bmi = input.bmi ?? 27; // US average if not provided

  // Exercise: higher BMI → less exercise (confounding)
  const exerciseBase = 150;
  const bmiExerciseEffect = (bmi - 25) * -8;
  const ageExerciseEffect = Math.max(0, (input.age - 40) * -2);
  const sexExerciseEffect = input.sex === "male" ? 20 : 0;
  const exerciseMean = Math.max(
    0,
    exerciseBase + bmiExerciseEffect + ageExerciseEffect + sexExerciseEffect
  );

  // Diet: higher BMI → worse diet (confounding)
  const dietBase = 0.45;
  const bmiDietEffect = (bmi - 25) * -0.02;
  const ageDietEffect = input.age > 60 ? 0.05 : 0;
  const educationDietEffect =
    input.education === "college" || input.education === "graduate" ? 0.1 : 0;
  const dietMean = Math.max(
    0,
    Math.min(1, dietBase + bmiDietEffect + ageDietEffect + educationDietEffect)
  );

  // Alcohol: sex-based with smoking adjustment
  const alcoholBase = input.sex === "male" ? 8 : 4;
  const smokingAlcoholEffect = input.smokingStatus === "current" ? 4 : 0;
  const ageAlcoholEffect = input.age > 65 ? -2 : 0;
  const alcoholMean = Math.max(
    0,
    alcoholBase + smokingAlcoholEffect + ageAlcoholEffect
  );

  // Sleep: BMI and age effects
  const sleepBase = 7.0;
  const bmiSleepEffect = bmi > 30 ? -0.3 : 0;
  const ageSleepEffect = input.age > 65 ? 0.3 : 0;
  const sleepMean = sleepBase + bmiSleepEffect + ageSleepEffect;

  // Social: age effect
  const socialBase = 4;
  const ageSocialEffect = input.age > 65 ? -0.5 : 0;
  const socialMean = Math.max(0, socialBase + ageSocialEffect);

  return {
    exercise: {
      aerobicMinutesPerWeek: exerciseMean,
      sd: 100, // High uncertainty
    },
    diet: {
      mediterraneanAdherence: dietMean,
      sd: 0.15,
    },
    alcohol: {
      drinksPerWeek: alcoholMean,
      sd: 5,
    },
    sleep: {
      hoursPerNight: sleepMean,
      sd: 1.0,
    },
    social: {
      closeRelationships: socialMean,
      sd: 2,
    },
  };
}

/**
 * Impute full PersonState from partial observations
 *
 * Logic:
 * - Start with default state for age/sex
 * - If BMI is observed, use it; otherwise impute
 * - Impute behaviors conditional on observed/imputed BMI
 * - Impute biomarkers conditional on behaviors
 */
export function imputeFullState(observed: PartialObservation): ImputationResult {
  const baseState = createDefaultState(observed.age, observed.sex);
  const imputedVariables: string[] = [];
  const uncertainty: Record<string, number> = {};

  // Set or impute BMI
  if (observed.bmi !== undefined) {
    baseState.biomarkers.bmi = observed.bmi;
  } else {
    const avgBMI = observed.sex === "male" ? 28.5 : 28.0;
    baseState.biomarkers.bmi = avgBMI;
    imputedVariables.push("biomarkers.bmi");
    uncertainty["biomarkers.bmi"] = 5;
  }

  const bmi = baseState.biomarkers.bmi!;

  // Impute behaviors
  const behaviors = imputeBehaviors({ ...observed, bmi });

  // Apply imputed exercise
  baseState.behaviors.exercise.aerobicMinutesPerWeek =
    behaviors.exercise.aerobicMinutesPerWeek;
  baseState.behaviors.exercise.strengthSessionsPerWeek =
    behaviors.exercise.aerobicMinutesPerWeek > 100 ? 2 : 1;
  imputedVariables.push("behaviors.exercise.aerobicMinutesPerWeek");
  uncertainty["behaviors.exercise.aerobicMinutesPerWeek"] =
    behaviors.exercise.sd;

  // Apply imputed diet
  baseState.behaviors.diet.mediterraneanAdherence =
    behaviors.diet.mediterraneanAdherence;
  baseState.behaviors.diet.vegetableServingsPerDay =
    2 + behaviors.diet.mediterraneanAdherence * 3;
  baseState.behaviors.diet.processedFoodPercent =
    40 - behaviors.diet.mediterraneanAdherence * 25;
  imputedVariables.push("behaviors.diet.mediterraneanAdherence");
  uncertainty["behaviors.diet.mediterraneanAdherence"] = behaviors.diet.sd;

  // Apply imputed alcohol
  baseState.behaviors.alcohol.drinksPerWeek = behaviors.alcohol.drinksPerWeek;
  imputedVariables.push("behaviors.alcohol.drinksPerWeek");
  uncertainty["behaviors.alcohol.drinksPerWeek"] = behaviors.alcohol.sd;

  // Apply imputed sleep
  baseState.behaviors.sleep.hoursPerNight = behaviors.sleep.hoursPerNight;
  imputedVariables.push("behaviors.sleep.hoursPerNight");
  uncertainty["behaviors.sleep.hoursPerNight"] = behaviors.sleep.sd;

  // Apply imputed social
  baseState.behaviors.social.closeRelationships =
    behaviors.social.closeRelationships;
  imputedVariables.push("behaviors.social.closeRelationships");
  uncertainty["behaviors.social.closeRelationships"] = behaviors.social.sd;

  // Set smoking status if observed
  if (observed.smokingStatus) {
    baseState.behaviors.smoking.status = observed.smokingStatus;
    if (observed.smokingStatus === "current") {
      baseState.behaviors.smoking.cigarettesPerDay = 15;
      baseState.behaviors.smoking.packYears = 10;
    } else if (observed.smokingStatus === "former") {
      baseState.behaviors.smoking.yearsQuit = 5;
      baseState.behaviors.smoking.packYears = 10;
    }
  }

  // Impute biomarkers from behaviors
  const exerciseMin = behaviors.exercise.aerobicMinutesPerWeek;
  const dietAdherence = behaviors.diet.mediterraneanAdherence;

  // Blood pressure
  const bpBase = 120;
  const bpBMIEffect = (bmi - 25) * 1.5;
  const bpExerciseEffect = (exerciseMin - 150) * -0.03;
  const bpDietEffect = (dietAdherence - 0.5) * -8;
  baseState.biomarkers.systolicBP =
    bpBase + bpBMIEffect + bpExerciseEffect + bpDietEffect;
  imputedVariables.push("biomarkers.systolicBP");
  uncertainty["biomarkers.systolicBP"] = 12;

  // Cholesterol
  baseState.biomarkers.ldlCholesterol = 110 + (bmi - 25) * 2 + (dietAdherence - 0.5) * -15;
  baseState.biomarkers.hdlCholesterol = 55 + (exerciseMin - 150) * 0.02;
  imputedVariables.push("biomarkers.ldlCholesterol");
  imputedVariables.push("biomarkers.hdlCholesterol");
  uncertainty["biomarkers.ldlCholesterol"] = 20;
  uncertainty["biomarkers.hdlCholesterol"] = 10;

  // Build simple field names and confidence scores for test compatibility
  const imputedFields: string[] = [];
  const confidence: Record<string, number> = {};

  // Map detailed paths to simple field names
  const fieldMappings: Record<string, { simple: string; maxSD: number }> = {
    "biomarkers.bmi": { simple: "bmi", maxSD: 10 },
    "behaviors.exercise.aerobicMinutesPerWeek": { simple: "exercise", maxSD: 200 },
    "behaviors.diet.mediterraneanAdherence": { simple: "diet", maxSD: 0.3 },
    "behaviors.alcohol.drinksPerWeek": { simple: "alcohol", maxSD: 15 },
    "behaviors.sleep.hoursPerNight": { simple: "sleep", maxSD: 2 },
    "behaviors.social.closeRelationships": { simple: "social", maxSD: 5 },
    "biomarkers.systolicBP": { simple: "systolicBP", maxSD: 30 },
    "biomarkers.ldlCholesterol": { simple: "ldlCholesterol", maxSD: 40 },
    "biomarkers.hdlCholesterol": { simple: "hdlCholesterol", maxSD: 20 },
  };

  for (const varPath of imputedVariables) {
    const mapping = fieldMappings[varPath];
    if (mapping) {
      if (!imputedFields.includes(mapping.simple)) {
        imputedFields.push(mapping.simple);
      }
      // Convert uncertainty (SD) to confidence (0-1): higher SD = lower confidence
      const sd = uncertainty[varPath] || mapping.maxSD;
      confidence[mapping.simple] = Math.max(0.1, 1 - sd / mapping.maxSD);
    }
  }

  // Add observed fields with confidence = 1.0
  if (observed.bmi !== undefined && !imputedFields.includes("bmi")) {
    confidence["bmi"] = 1.0;
  }
  if (observed.smokingStatus && !imputedFields.includes("smokingStatus")) {
    confidence["smokingStatus"] = 1.0;
  }
  if (observed.education && !imputedFields.includes("education")) {
    confidence["education"] = 1.0;
  }

  return {
    state: baseState,
    imputedFields,
    confidence,
    imputedVariables,
    uncertainty,
  };
}

/**
 * Create a "typical" person with target behavior
 *
 * This is what naive comparison would use - a typical exerciser also has
 * better diet, lower BMI, less smoking (confounding correlation).
 */
export function createTypicalStateWithBehavior(
  targetBehavior: {
    variable: "exercise" | "diet" | "smoking" | "alcohol" | "sleep";
    value: Partial<Behaviors>;
  },
  age: number,
  sex: "male" | "female"
): PersonState {
  const state = createDefaultState(age, sex);

  if (targetBehavior.variable === "exercise" && targetBehavior.value.exercise) {
    Object.assign(state.behaviors.exercise, targetBehavior.value.exercise);

    // Typical exercisers also have healthier correlates
    state.behaviors.diet.mediterraneanAdherence = 0.6;
    state.behaviors.diet.vegetableServingsPerDay = 4;
    state.behaviors.diet.processedFoodPercent = 20;
    state.biomarkers.bmi = 24;
    state.behaviors.smoking.status = "never";
    state.behaviors.alcohol.drinksPerWeek = 3;
  } else if (targetBehavior.variable === "diet" && targetBehavior.value.diet) {
    Object.assign(state.behaviors.diet, targetBehavior.value.diet);

    // Typical healthy eaters also exercise more
    state.behaviors.exercise.aerobicMinutesPerWeek = 180;
    state.biomarkers.bmi = 23;
    state.behaviors.smoking.status = "never";
  } else if (
    targetBehavior.variable === "smoking" &&
    targetBehavior.value.smoking
  ) {
    Object.assign(state.behaviors.smoking, targetBehavior.value.smoking);

    if (state.behaviors.smoking.status === "never") {
      state.behaviors.exercise.aerobicMinutesPerWeek = 160;
      state.behaviors.diet.mediterraneanAdherence = 0.55;
      state.biomarkers.bmi = 26;
    }
  } else if (
    targetBehavior.variable === "alcohol" &&
    targetBehavior.value.alcohol
  ) {
    Object.assign(state.behaviors.alcohol, targetBehavior.value.alcohol);
  } else if (targetBehavior.variable === "sleep" && targetBehavior.value.sleep) {
    Object.assign(state.behaviors.sleep, targetBehavior.value.sleep);
  }

  return state;
}

/**
 * Deep copy utility
 */
export function deepCopy<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}
