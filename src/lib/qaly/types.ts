/**
 * Structured QALY calculation types
 *
 * Causal chain: Intervention → Mechanism → Condition → QALY
 *
 * QALY = ∫ Q(t) × S(t) dt from now to death
 *
 * An intervention modifies:
 * - Mechanisms (blood pressure, inflammation, etc.)
 * - Which affect conditions (heart disease, depression, etc.)
 * - Which affect mortality S(t) and quality Q(t)
 */

import type { Mechanism } from "./mechanisms";

/**
 * Statistical distribution for uncertain parameters
 */
export type Distribution =
  | { type: "point"; value: number }
  | { type: "normal"; mean: number; sd: number }
  | { type: "lognormal"; logMean: number; logSd: number } // For HRs, RRs
  | { type: "beta"; alpha: number; beta: number } // For probabilities, utilities
  | { type: "uniform"; min: number; max: number };

/**
 * Mortality effect of an intervention
 */
export interface MortalityEffect {
  /** Hazard ratio (HR < 1 = reduced mortality, HR > 1 = increased) */
  hazardRatio: Distribution;

  /** Which causes of death are affected (null = all-cause) */
  affectedCauses?: string[];

  /** Delay before effect begins (years) */
  onsetDelay: number;

  /** How quickly effect reaches full strength (years) */
  rampUpPeriod: number;

  /** Does effect persist after stopping? (years, null = permanent) */
  persistenceAfterStopping?: number;

  /** Effect decay rate per year (0 = no decay, 1 = fully decays in 1 year) */
  decayRate: number;
}

/**
 * EQ-5D-5L dimensions for quality of life
 * These are the standard QALY measurement domains
 */
export type EQ5DDimension =
  | "mobility"
  | "selfCare"
  | "usualActivities"
  | "painDiscomfort"
  | "anxietyDepression";

/**
 * Health conditions/states that affect quality
 * Maps to our GBD disability weights
 */
export type HealthCondition =
  // Cardiovascular
  | "heart_failure"
  | "angina"
  | "stroke"
  | "hypertension"
  // Metabolic
  | "diabetes"
  | "obesity"
  // Respiratory
  | "copd"
  | "asthma"
  // Mental health
  | "depression"
  | "anxiety"
  | "cognitive_impairment"
  // Musculoskeletal
  | "back_pain"
  | "osteoarthritis"
  | "osteoporosis"
  // Cancer
  | "cancer"
  | "melanoma"
  | "non_melanoma_skin_cancer"
  // Sensory
  | "vision_loss"
  | "hearing_loss"
  // Other
  | "fatigue"
  | "sleep_disorder"
  | "general_wellbeing";

/**
 * Effect on a specific health condition/domain
 */
export interface ConditionEffect {
  /** Which condition is affected */
  condition: HealthCondition;

  /** Change in relative risk of developing condition (RR < 1 = protective) */
  incidenceRR?: Distribution;

  /** Change in severity if condition exists (negative = less severe) */
  severityChange?: Distribution;

  /** Change in probability of remission (positive = more likely to recover) */
  remissionChange?: Distribution;
}

/**
 * Effect on EQ-5D dimension directly
 */
export interface DimensionEffect {
  dimension: EQ5DDimension;
  /** Change in dimension score (-0.5 to +0.5 typical range) */
  change: Distribution;
}

/**
 * Quality of life effect of an intervention
 * Decomposed into condition-specific and dimension-specific effects
 */
export interface QualityEffect {
  /** Effects mediated through specific health conditions */
  conditionEffects: ConditionEffect[];

  /** Direct effects on EQ-5D dimensions (not mediated through conditions) */
  directDimensionEffects: DimensionEffect[];

  /** Hedonic/subjective wellbeing effect (independent of health) */
  subjectiveWellbeing?: Distribution;

  /** Delay before effect begins (years) */
  onsetDelay: number;

  /** Does effect persist after stopping? */
  persistenceAfterStopping?: number;

  /** Effect decay rate per year */
  decayRate: number;
}

/**
 * Effect on a specific biological mechanism
 */
export interface MechanismEffect {
  /** Which mechanism is affected */
  mechanism: Mechanism;

  /** Effect size as standardized effect (Cohen's d) or relative change */
  effectSize: Distribution;

  /** Direction: positive means improvement/increase */
  direction: "increase" | "decrease";

  /** How this converts to mechanism units (e.g., "mmHg for BP", "% for inflammation") */
  units?: string;

  /** Evidence quality for this specific mechanism effect */
  evidenceQuality: "strong" | "moderate" | "weak";

  /** Key source for this mechanism effect */
  source?: string;
}

/**
 * Time and resource costs of an intervention
 */
export interface InterventionCosts {
  /** Hours per week spent on the intervention */
  hoursPerWeek: Distribution;

  /** Financial cost per year (USD) */
  annualCost: Distribution;

  /** Disutility during the intervention itself (e.g., exercise is unpleasant) */
  activityDisutility: Distribution;
}

/**
 * Complete intervention effect specification
 */
export interface InterventionEffect {
  /** What is being analyzed */
  description: string;

  /** Category for grouping */
  category: "exercise" | "diet" | "sleep" | "substance" | "medical" | "stress" | "social" | "other";

  /** PRIMARY: Effects on biological mechanisms */
  mechanismEffects: MechanismEffect[];

  /** DERIVED: Effect on mortality (can be computed from mechanisms) */
  mortality: MortalityEffect | null;

  /** DERIVED: Effect on quality of life (can be computed from mechanisms) */
  quality: QualityEffect | null;

  /** Costs and time requirements */
  costs: InterventionCosts | null;

  /** Confidence in the overall evidence */
  evidenceQuality: "high" | "moderate" | "low" | "very-low";

  /** Key evidence sources */
  keySources: {
    citation: string;
    studyType: "meta-analysis" | "rct" | "cohort" | "case-control" | "other";
    sampleSize?: number;
    contribution: string; // What this source contributes to the estimate
  }[];

  /** Important caveats */
  caveats: string[];

  /** How user profile affects this estimate */
  profileAdjustments: string[];
}

/**
 * Simulation options
 */
export interface SimulationOptions {
  /** Number of Monte Carlo iterations */
  nSimulations?: number;

  /** Apply confounding adjustment (default: true) */
  applyConfounding?: boolean;

  /** Override confounding config (uses category default if not provided) */
  confoundingOverride?: {
    alpha: number;
    beta: number;
  };

  /** Primary evidence type for confounding adjustment */
  evidenceType?: "meta-analysis" | "rct" | "cohort" | "case-control" | "review" | "other";
}

/**
 * Confounding analysis included in simulation result
 */
export interface ConfoundingResult {
  /** Was confounding adjustment applied? */
  applied: boolean;

  /** Expected causal fraction (mean of Beta prior) */
  expectedCausalFraction: number;

  /** 95% CI for causal fraction */
  causalFractionCI: { low: number; high: number };

  /** E-value for the unadjusted mortality HR */
  eValue: {
    point: number;
    ciLow: number;
    interpretation: string;
  };

  /** Comparison of adjusted vs unadjusted estimates */
  comparison: {
    unadjustedMedian: number;
    adjustedMedian: number;
    reductionPercent: number;
  };
}

/**
 * Result of Monte Carlo QALY simulation
 */
export interface QALYSimulationResult {
  /** Point estimate (median of posterior) */
  median: number;

  /** Mean of posterior */
  mean: number;

  /** 95% credible interval */
  ci95: { low: number; high: number };

  /** 50% credible interval */
  ci50: { low: number; high: number };

  /** Probability of positive effect */
  probPositive: number;

  /** Probability of > 1 year QALY gain */
  probMoreThanOneYear: number;

  /** Full distribution (percentiles) */
  percentiles: { p: number; value: number }[];

  /** Breakdown by component */
  breakdown: {
    mortalityQALYs: { median: number; ci95: { low: number; high: number } };
    qualityQALYs: { median: number; ci95: { low: number; high: number } };
    costQALYs: { median: number; ci95: { low: number; high: number } };
  };

  /** Confounding analysis (if applied) */
  confounding?: ConfoundingResult;

  /** Number of simulations run */
  nSimulations: number;
}
