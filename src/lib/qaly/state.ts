/**
 * PersonState schema for state-centric QALY modeling
 *
 * Architecture:
 * - A person's STATE determines their hazard rates (mortality + quality)
 * - "Interventions" are just DIFFS between states
 * - This unifies intervention modeling: all interventions are state changes
 *
 * Structure:
 * - Demographics: immutable characteristics (age, sex, ethnicity)
 * - Conditions: diagnosed health conditions with severity/treatment status
 * - Biomarkers: measured or imputed physiological markers
 * - Behaviors: the adjustable "dials" (exercise, diet, sleep, substances, social)
 * - Environment: external factors (air quality, walkability, healthcare access)
 *
 * Usage:
 * 1. Create baseline state: createDefaultState(age, sex)
 * 2. Apply intervention: updateState(state, { behaviors: { exercise: ... }})
 * 3. Calculate hazard rates from both states
 * 4. Compute QALY difference
 *
 * This approach enables:
 * - Consistent modeling across all intervention types
 * - Natural handling of interaction effects
 * - Direct comparison of "what if I do X vs Y"
 * - Clear separation of immutable vs modifiable factors
 */

import type { HealthCondition } from "./types";

/**
 * Diagnosed health condition with metadata
 */
export interface Condition {
  type: HealthCondition;
  severity?: "mild" | "moderate" | "severe";
  controlled?: boolean; // on treatment
  yearDiagnosed?: number;
  medications?: string[];
}

/**
 * Measured or imputed biomarkers
 */
export interface Biomarkers {
  // Cardiovascular
  systolicBP?: number; // mmHg
  diastolicBP?: number;
  restingHR?: number; // bpm

  // Lipids
  totalCholesterol?: number; // mg/dL
  ldlCholesterol?: number;
  hdlCholesterol?: number;
  triglycerides?: number;

  // Metabolic
  fastingGlucose?: number; // mg/dL
  hba1c?: number; // %

  // Anthropometric
  bmi?: number;
  waistCircumference?: number; // cm
  bodyFatPercent?: number;

  // Inflammatory
  crp?: number; // mg/L

  // Kidney
  egfr?: number; // mL/min/1.73m²
}

/**
 * Lifestyle behaviors (the "dials" we can adjust)
 */
export interface Behaviors {
  // Exercise
  exercise: {
    aerobicMinutesPerWeek: number;
    strengthSessionsPerWeek: number;
    stepsPerDay?: number;
  };

  // Diet
  diet: {
    mediterraneanAdherence: number; // 0-1 scale
    processedFoodPercent: number; // % of calories
    vegetableServingsPerDay: number;
    fruitServingsPerDay: number;
    fishServingsPerWeek: number;
    redMeatServingsPerWeek: number;
    sugarGramsPerDay?: number;
    fiberGramsPerDay?: number;
    sodiumMgPerDay?: number;
  };

  // Substances
  alcohol: {
    drinksPerWeek: number;
    bingeFrequency: "never" | "monthly" | "weekly" | "daily";
  };

  smoking: {
    status: "never" | "former" | "current";
    packYears?: number; // for current/former
    yearsQuit?: number; // for former
    cigarettesPerDay?: number; // for current
  };

  // Sleep
  sleep: {
    hoursPerNight: number;
    quality: "poor" | "fair" | "good" | "excellent";
    consistentSchedule: boolean;
  };

  // Social
  social: {
    closeRelationships: number;
    weeklyInteractionHours: number;
    livesAlone: boolean;
    partnerStatus: "single" | "partnered" | "married" | "widowed";
  };

  // Stress management
  stress: {
    chronicStressLevel: "low" | "moderate" | "high";
    meditationMinutesPerWeek: number;
    therapyOrCounseling: boolean;
  };

  // Medical adherence
  medical: {
    regularCheckups: boolean;
    medicationAdherence: "poor" | "moderate" | "good" | "excellent";
    screeningsUpToDate: boolean;
  };
}

/**
 * Environmental factors
 */
export interface Environment {
  airQualityAQI?: number;
  walkabilityScore?: number; // 0-100
  greenSpaceAccess?: boolean;
  noisePollution?: "low" | "moderate" | "high";
  healthcareAccess?: "poor" | "moderate" | "good" | "excellent";
}

/**
 * Complete person state
 */
export interface PersonState {
  // Immutable demographics
  demographics: {
    birthYear: number;
    sex: "male" | "female";
    ethnicity?: string; // optional, affects some risk calculations
  };

  // Current diagnosed conditions
  conditions: Condition[];

  // Measured or imputed biomarkers
  biomarkers: Biomarkers;

  // Lifestyle behaviors (the "dials" we can adjust)
  behaviors: Behaviors;

  // Environmental factors
  environment: Environment;
}

/**
 * Validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Deep partial type for state updates
 */
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object
    ? T[P] extends Array<infer U>
      ? Array<U>
      : DeepPartial<T[P]>
    : T[P];
};

/**
 * Create default state (average person)
 */
export function createDefaultState(
  age: number,
  sex: "male" | "female"
): PersonState {
  const currentYear = new Date().getFullYear();

  return {
    demographics: {
      birthYear: currentYear - age,
      sex,
    },

    conditions: [],

    biomarkers: {
      // Average values for healthy adult
      systolicBP: 120,
      diastolicBP: 80,
      restingHR: 70,
      totalCholesterol: 190,
      ldlCholesterol: 110,
      hdlCholesterol: 55,
      triglycerides: 100,
      fastingGlucose: 90,
      hba1c: 5.4,
      bmi: 25,
      egfr: 90,
    },

    behaviors: {
      exercise: {
        aerobicMinutesPerWeek: 150, // CDC recommendation
        strengthSessionsPerWeek: 2,
        stepsPerDay: 7000,
      },

      diet: {
        mediterraneanAdherence: 0.5, // moderate
        processedFoodPercent: 30,
        vegetableServingsPerDay: 3,
        fruitServingsPerDay: 2,
        fishServingsPerWeek: 1,
        redMeatServingsPerWeek: 3,
        sugarGramsPerDay: 50,
        fiberGramsPerDay: 25,
        sodiumMgPerDay: 3000,
      },

      alcohol: {
        drinksPerWeek: 3,
        bingeFrequency: "never",
      },

      smoking: {
        status: "never",
      },

      sleep: {
        hoursPerNight: 7,
        quality: "good",
        consistentSchedule: true,
      },

      social: {
        closeRelationships: 5,
        weeklyInteractionHours: 10,
        livesAlone: false,
        partnerStatus: "partnered",
      },

      stress: {
        chronicStressLevel: "moderate",
        meditationMinutesPerWeek: 0,
        therapyOrCounseling: false,
      },

      medical: {
        regularCheckups: true,
        medicationAdherence: "good",
        screeningsUpToDate: true,
      },
    },

    environment: {
      walkabilityScore: 50,
      greenSpaceAccess: true,
      noisePollution: "moderate",
      healthcareAccess: "good",
    },
  };
}

/**
 * Merge partial state update (for interventions)
 */
export function updateState(
  state: PersonState,
  updates: DeepPartial<PersonState>
): PersonState {
  return {
    demographics: {
      ...state.demographics,
      ...updates.demographics,
    },
    conditions: updates.conditions ?? state.conditions,
    biomarkers: {
      ...state.biomarkers,
      ...updates.biomarkers,
    },
    behaviors: {
      exercise: {
        ...state.behaviors.exercise,
        ...updates.behaviors?.exercise,
      },
      diet: {
        ...state.behaviors.diet,
        ...updates.behaviors?.diet,
      },
      alcohol: {
        ...state.behaviors.alcohol,
        ...updates.behaviors?.alcohol,
      },
      smoking: {
        ...state.behaviors.smoking,
        ...updates.behaviors?.smoking,
      },
      sleep: {
        ...state.behaviors.sleep,
        ...updates.behaviors?.sleep,
      },
      social: {
        ...state.behaviors.social,
        ...updates.behaviors?.social,
      },
      stress: {
        ...state.behaviors.stress,
        ...updates.behaviors?.stress,
      },
      medical: {
        ...state.behaviors.medical,
        ...updates.behaviors?.medical,
      },
    },
    environment: {
      ...state.environment,
      ...updates.environment,
    },
  };
}

/**
 * Calculate age from state
 */
export function getAge(state: PersonState, year?: number): number {
  const targetYear = year ?? new Date().getFullYear();
  return targetYear - state.demographics.birthYear;
}

/**
 * Validate state (check for impossible combinations)
 */
export function validateState(state: PersonState): ValidationResult {
  const errors: string[] = [];

  // Validate biomarkers
  if (state.biomarkers.bmi !== undefined) {
    if (state.biomarkers.bmi < 10 || state.biomarkers.bmi > 80) {
      errors.push("BMI out of reasonable range (10-80)");
    }
  }

  if (state.biomarkers.systolicBP !== undefined) {
    if (
      state.biomarkers.systolicBP < 60 ||
      state.biomarkers.systolicBP > 250
    ) {
      errors.push("Systolic BP out of reasonable range (60-250)");
    }
  }

  if (state.biomarkers.diastolicBP !== undefined) {
    if (
      state.biomarkers.diastolicBP < 40 ||
      state.biomarkers.diastolicBP > 150
    ) {
      errors.push("Diastolic BP out of reasonable range (40-150)");
    }
  }

  if (state.biomarkers.restingHR !== undefined) {
    if (state.biomarkers.restingHR < 30 || state.biomarkers.restingHR > 200) {
      errors.push("Resting HR out of reasonable range (30-200)");
    }
  }

  // Validate exercise
  if (state.behaviors.exercise.aerobicMinutesPerWeek < 0) {
    errors.push("Exercise minutes cannot be negative");
  }

  if (state.behaviors.exercise.strengthSessionsPerWeek < 0) {
    errors.push("Strength sessions cannot be negative");
  }

  // Validate smoking
  if (state.behaviors.smoking.status === "former") {
    if (state.behaviors.smoking.packYears === undefined) {
      errors.push("Former smokers must have packYears");
    }
    if (state.behaviors.smoking.yearsQuit === undefined) {
      errors.push("Former smokers must have yearsQuit");
    }
  }

  if (state.behaviors.smoking.status === "current") {
    if (state.behaviors.smoking.cigarettesPerDay === undefined) {
      errors.push("Current smokers must have cigarettesPerDay");
    }
  }

  // Validate alcohol
  if (state.behaviors.alcohol.drinksPerWeek < 0) {
    errors.push("Drinks per week cannot be negative");
  }

  // Validate sleep
  if (
    state.behaviors.sleep.hoursPerNight < 0 ||
    state.behaviors.sleep.hoursPerNight > 24
  ) {
    errors.push("Sleep hours must be between 0 and 24");
  }

  // Validate diet
  if (
    state.behaviors.diet.mediterraneanAdherence < 0 ||
    state.behaviors.diet.mediterraneanAdherence > 1
  ) {
    errors.push("Mediterranean adherence must be between 0 and 1");
  }

  if (
    state.behaviors.diet.processedFoodPercent < 0 ||
    state.behaviors.diet.processedFoodPercent > 100
  ) {
    errors.push("Processed food percent must be between 0 and 100");
  }

  return {
    valid: errors.length === 0,
    errors,
  };
}
