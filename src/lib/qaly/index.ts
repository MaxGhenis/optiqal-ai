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
export { simulateQALYImpact, qalyYearsToMinutes } from "./simulate";
