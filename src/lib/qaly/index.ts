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

// Derive mortality from mechanisms
export {
  deriveMortalityFromMechanisms,
  deriveMortalityWithBreakdown,
  type MechanismMortalityBreakdown,
  type MortalityWithBreakdown,
} from "./derive-mortality";

// Derive quality of life from mechanisms
export {
  deriveQualityFromMechanisms,
  deriveQualityWithBreakdown,
  type MechanismQualityBreakdown,
  type QualityWithBreakdown,
} from "./derive-quality";

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

// Calibrated confounding priors (RCT vs observational calibration)
export {
  CALIBRATION_DATA,
  CALIBRATED_PRIORS,
  INTERVENTION_SPECIFIC_PRIORS,
  getCalibratedPrior,
  PRIOR_COMPARISON,
  type CalibrationPoint,
} from "./confounding-calibrated";

// Person state schema (state-centric modeling)
export {
  type PersonState,
  type Condition,
  type Biomarkers,
  type Behaviors,
  type Environment,
  type ValidationResult,
  type DeepPartial,
  createDefaultState,
  updateState,
  getAge,
  validateState,
} from "./state";

// State → Hazard calculator
export {
  type StateHazardResult,
  computeStateHazards,
  computeStateHazardsWithUncertainty,
  getLifeExpectancy,
  getAnnualMortalityFromState,
} from "./state-hazard";

// Risk factor hazard database
export {
  type HRWithUncertainty,
  type HazardValue,
  type RiskContext,
  type HazardType,
  type RiskCategory,
  type StudyType,
  type Source,
  type RiskFactorHazard,
  type HazardRatioSet,
  type CauseOfDeath,
  RISK_FACTORS,
  combineHazardRatios,
  getHazardRatiosForState,
  getCauseSpecificHR,
} from "./risk-factors";

// State-based lifecycle simulator
export {
  type YearlyTrajectory,
  type QALYDistribution,
  type LifeExpectancy,
  type StateLifecycleResult,
  type SimulationOptions as StateLifecycleSimulationOptions,
  simulateLifecycleFromState,
  getQualityWeightFromState,
  getBaseQualityByAge,
} from "./state-lifecycle";

// State comparison and intervention impact (state-diff)
export {
  type StateComparisonResult,
  type SimulationOptions as StateDiffSimulationOptions,
  compareStates,
  computeInterventionImpact,
  compareInterventions,
  identifyStateChanges,
} from "./state-diff";

// Imputation (behavior imputation and causal DAG)
export {
  type PartialObservation,
  type ImputationResult,
  type ImputationInput,
  type ImputedBehaviors,
  type CausalEffect,
  imputeFullState,
  createTypicalStateWithBehavior,
  deepCopy,
  CAUSAL_DAG,
} from "./imputation";

// Counterfactual simulation (causal intervention with imputation)
export {
  type CounterfactualResult,
  type Intervention,
  type CounterfactualOptions,
  simulateCausalIntervention,
} from "./counterfactual";

// Paper results (single source of truth for documentation)
export {
  type InterventionResult,
  type ConfoundingParams,
  type PaperResults,
  PAPER_RESULTS,
  SEED,
  formatQaly,
  formatLifeYears,
  formatMonths,
  formatCI,
  getIntervention,
  getTopInterventions,
  getInterventionsByCategory,
} from "./paper-results";
