/**
 * Biological mechanisms linking interventions to health outcomes
 *
 * Structure: Intervention → Mechanism → Condition
 *
 * This allows us to:
 * 1. Ask Claude about effect on specific mechanisms
 * 2. Use known mechanism → condition relationships
 * 3. Properly propagate uncertainty through the causal chain
 */

import type { Distribution, HealthCondition } from "./types";

/**
 * Biological mechanisms that mediate health effects
 */
export type Mechanism =
  // Cardiovascular mechanisms
  | "blood_pressure"
  | "lipid_profile" // LDL, HDL, triglycerides
  | "endothelial_function"
  | "arterial_stiffness"
  | "heart_rate_variability"
  | "cardiac_output"

  // Metabolic mechanisms
  | "insulin_sensitivity"
  | "glucose_regulation"
  | "adiposity" // Body fat distribution
  | "metabolic_rate"
  | "mitochondrial_function"

  // Inflammatory/Immune
  | "systemic_inflammation" // CRP, IL-6, TNF-α
  | "oxidative_stress"
  | "immune_function"
  | "gut_microbiome"

  // Neurological
  | "neuroplasticity"
  | "bdnf_levels" // Brain-derived neurotrophic factor
  | "neurotransmitter_balance" // Serotonin, dopamine, etc.
  | "sleep_quality"
  | "stress_hormones" // Cortisol, adrenaline
  | "cognitive_reserve"

  // Musculoskeletal
  | "muscle_mass"
  | "bone_density"
  | "joint_health"
  | "balance_proprioception"

  // Cellular
  | "telomere_length"
  | "cellular_senescence"
  | "autophagy"
  | "dna_repair"

  // Respiratory
  | "lung_function" // FEV1, VO2max
  | "oxygen_delivery";

/**
 * How a mechanism affects a condition
 */
export interface MechanismConditionLink {
  condition: HealthCondition;
  /** Effect direction: "protective" means better mechanism → lower risk */
  direction: "protective" | "harmful";
  /** Strength of evidence */
  evidenceStrength: "strong" | "moderate" | "weak";
  /** Relative contribution of this mechanism to condition risk */
  relativeImportance: number; // 0-1, mechanisms for a condition should sum to ~1
  /** Source */
  source: string;
}

/**
 * Known mechanism → condition relationships
 */
export const MECHANISM_CONDITION_LINKS: Record<Mechanism, MechanismConditionLink[]> = {
  // Cardiovascular mechanisms
  blood_pressure: [
    { condition: "stroke", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.4, source: "INTERSTROKE" },
    { condition: "heart_failure", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.3, source: "Framingham" },
    { condition: "angina", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.3, source: "Multiple RCTs" },
    { condition: "cognitive_impairment", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.2, source: "SPRINT-MIND" },
    { condition: "vision_loss", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Observational" },
  ],

  lipid_profile: [
    { condition: "angina", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.4, source: "CTT meta-analysis" },
    { condition: "stroke", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.2, source: "CTT meta-analysis" },
    { condition: "heart_failure", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Observational" },
  ],

  endothelial_function: [
    { condition: "angina", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.2, source: "Mechanistic studies" },
    { condition: "stroke", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Observational" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "weak", relativeImportance: 0.1, source: "Emerging" },
  ],

  arterial_stiffness: [
    { condition: "heart_failure", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.2, source: "Multiple cohorts" },
    { condition: "stroke", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Observational" },
  ],

  heart_rate_variability: [
    { condition: "heart_failure", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Observational" },
    { condition: "anxiety", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Polyvagal theory" },
  ],

  cardiac_output: [
    { condition: "heart_failure", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.25, source: "Clinical" },
    { condition: "fatigue", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Exercise studies" },
  ],

  // Metabolic mechanisms
  insulin_sensitivity: [
    { condition: "diabetes", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.5, source: "DPP, multiple RCTs" },
    { condition: "obesity", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.3, source: "Metabolic studies" },
    { condition: "heart_failure", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Observational" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Emerging" },
  ],

  glucose_regulation: [
    { condition: "diabetes", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.3, source: "UKPDS, DCCT" },
    { condition: "vision_loss", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.25, source: "DCCT (retinopathy)" },
  ],

  adiposity: [
    { condition: "obesity", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.6, source: "Definition" },
    { condition: "diabetes", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.3, source: "Multiple studies" },
    { condition: "osteoarthritis", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.3, source: "Mechanical + inflammatory" },
    { condition: "back_pain", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Observational" },
    { condition: "sleep_disorder", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.4, source: "Sleep apnea studies" },
  ],

  metabolic_rate: [
    { condition: "obesity", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Metabolic studies" },
    { condition: "fatigue", direction: "protective", evidenceStrength: "weak", relativeImportance: 0.1, source: "Indirect" },
  ],

  mitochondrial_function: [
    { condition: "fatigue", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.25, source: "Mitochondrial medicine" },
    { condition: "heart_failure", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Emerging" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "weak", relativeImportance: 0.1, source: "Emerging" },
  ],

  // Inflammatory/Immune
  systemic_inflammation: [
    { condition: "heart_failure", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.15, source: "CRP studies" },
    { condition: "diabetes", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Inflammatory pathway" },
    { condition: "depression", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Inflammatory hypothesis" },
    { condition: "cognitive_impairment", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Neuroinflammation" },
    { condition: "cancer", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Tumor microenvironment" },
  ],

  oxidative_stress: [
    { condition: "cognitive_impairment", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Oxidative damage theory" },
    { condition: "vision_loss", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.2, source: "AMD studies" },
    { condition: "cancer", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.1, source: "DNA damage" },
  ],

  immune_function: [
    { condition: "cancer", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.25, source: "Immunosurveillance" },
    { condition: "asthma", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Immune regulation" },
  ],

  gut_microbiome: [
    { condition: "obesity", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Emerging" },
    { condition: "depression", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Gut-brain axis" },
    { condition: "anxiety", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Gut-brain axis" },
  ],

  // Neurological
  neuroplasticity: [
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.25, source: "Cognitive reserve theory" },
    { condition: "depression", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Neuroplasticity hypothesis" },
  ],

  bdnf_levels: [
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.2, source: "BDNF studies" },
    { condition: "depression", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.25, source: "Neurotrophic hypothesis" },
  ],

  neurotransmitter_balance: [
    { condition: "depression", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.35, source: "Monoamine hypothesis" },
    { condition: "anxiety", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.4, source: "GABA/serotonin" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Cholinergic hypothesis" },
  ],

  sleep_quality: [
    { condition: "sleep_disorder", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.8, source: "Definition" },
    { condition: "depression", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.2, source: "Sleep-mood link" },
    { condition: "anxiety", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "Sleep-anxiety" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.15, source: "Glymphatic" },
    { condition: "obesity", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Hormonal" },
    { condition: "fatigue", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.4, source: "Direct" },
  ],

  stress_hormones: [
    { condition: "anxiety", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.3, source: "HPA axis" },
    { condition: "depression", direction: "harmful", evidenceStrength: "strong", relativeImportance: 0.2, source: "Cortisol studies" },
    { condition: "cognitive_impairment", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Hippocampal damage" },
    { condition: "sleep_disorder", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Arousal" },
  ],

  cognitive_reserve: [
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.3, source: "Cognitive reserve theory" },
  ],

  // Musculoskeletal
  muscle_mass: [
    { condition: "fatigue", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Sarcopenia studies" },
    { condition: "obesity", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Metabolic" },
    { condition: "osteoporosis", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Mechanical loading" },
    { condition: "back_pain", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.25, source: "Core strength" },
  ],

  bone_density: [
    { condition: "osteoporosis", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.7, source: "Definition" },
  ],

  joint_health: [
    { condition: "osteoarthritis", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.5, source: "Cartilage studies" },
    { condition: "back_pain", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.3, source: "Disc health" },
  ],

  balance_proprioception: [
    { condition: "osteoporosis", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Fall prevention" },
  ],

  // Cellular
  telomere_length: [
    { condition: "cancer", direction: "protective", evidenceStrength: "weak", relativeImportance: 0.05, source: "Conflicting evidence" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "weak", relativeImportance: 0.05, source: "Aging marker" },
  ],

  cellular_senescence: [
    { condition: "cancer", direction: "harmful", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Senescence-associated secretory phenotype" },
  ],

  autophagy: [
    { condition: "cancer", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Cellular cleanup" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.1, source: "Protein aggregation" },
  ],

  dna_repair: [
    { condition: "cancer", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.2, source: "Mutation prevention" },
  ],

  // Respiratory
  lung_function: [
    { condition: "copd", direction: "protective", evidenceStrength: "strong", relativeImportance: 0.7, source: "FEV1 studies" },
    { condition: "asthma", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.3, source: "Airway function" },
    { condition: "fatigue", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.15, source: "VO2max" },
  ],

  oxygen_delivery: [
    { condition: "fatigue", direction: "protective", evidenceStrength: "moderate", relativeImportance: 0.2, source: "Oxygen utilization" },
    { condition: "cognitive_impairment", direction: "protective", evidenceStrength: "weak", relativeImportance: 0.05, source: "Brain oxygenation" },
  ],
};

/**
 * Get all mechanisms that affect a given condition
 */
export function getMechanismsForCondition(
  condition: HealthCondition
): { mechanism: Mechanism; link: MechanismConditionLink }[] {
  const results: { mechanism: Mechanism; link: MechanismConditionLink }[] = [];

  for (const [mechanism, links] of Object.entries(MECHANISM_CONDITION_LINKS)) {
    for (const link of links) {
      if (link.condition === condition) {
        results.push({ mechanism: mechanism as Mechanism, link });
      }
    }
  }

  return results.sort((a, b) => b.link.relativeImportance - a.link.relativeImportance);
}

/**
 * Get all conditions affected by a given mechanism
 */
export function getConditionsForMechanism(
  mechanism: Mechanism
): MechanismConditionLink[] {
  return MECHANISM_CONDITION_LINKS[mechanism] || [];
}
