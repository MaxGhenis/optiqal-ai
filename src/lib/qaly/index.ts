/**
 * QALY calculation system
 *
 * Causal chain: Intervention → Mechanism → Condition → QALY
 *
 * Usage:
 * 1. Call Claude with mechanism elicitation prompt
 * 2. Parse response into InterventionEffect
 * 3. Use mechanism→condition mappings to compute condition effects
 * 4. Run Monte Carlo simulation to get QALY distribution
 */

// Types
export * from "./types";

// Mechanism graph
export {
  type Mechanism,
  MECHANISM_CONDITION_LINKS,
  getMechanismsForCondition,
  getConditionsForMechanism,
} from "./mechanisms";

// Condition data
export {
  DISABILITY_WEIGHTS,
  BASELINE_INCIDENCE_PER_1000,
  getBaselineIncidence,
  getDisabilityWeight,
  CONDITION_TO_DIMENSIONS,
} from "./conditions";

// Prompt generation
export {
  ALL_MECHANISMS,
  MECHANISM_ELICITATION_PROMPT,
  generateElicitationPrompt,
} from "./prompt";

// Simulation
export {
  simulateQALYImpact,
  simulateQALYImpactRigorous,
  qalyYearsToMinutes,
  type RigorousSimulationResult,
  type RigorousSimulationOptions,
} from "./simulate";

// Precomputed interventions
export {
  PRECOMPUTED_INTERVENTIONS,
  matchIntervention,
  getPrecomputedEffect,
  type PrecomputedIntervention,
  type MatchResult,
} from "./precomputed";

// Confounding adjustment (whatnut methodology)
export {
  CONFOUNDING_BY_CATEGORY,
  EVIDENCE_ADJUSTMENTS,
  getConfoundingConfig,
  sampleCausalFraction,
  getExpectedCausalFraction,
  getCausalFractionCI,
  adjustHazardRatio,
  adjustDistribution,
  calculateEValue,
  calculateEValueForCI,
  analyzeConfounding,
  type ConfoundingConfig,
  type ConfoundingAnalysis,
} from "./confounding";

// DSL parser for YAML intervention definitions
export {
  parseDistribution,
  parseIntervention,
  parseConfounding,
  formatDistribution,
  getDistributionMean,
  getDistributionSD,
  type YAMLIntervention,
} from "./dsl-parser";

// Rigorous lifecycle model (whatnut methodology)
export {
  CDC_LIFE_TABLE,
  getSurvivalProbability,
  getAnnualMortalityRate,
  CAUSE_FRACTIONS,
  getCauseFraction,
  applyDiscount,
  getDiscountedQALY,
  calculateLifecycleQALYs,
  hrToPathwayHRs,
  STANDARD_PATHWAY_HRS,
  type PathwayHRs,
  type LifecycleResult,
} from "./lifecycle";
