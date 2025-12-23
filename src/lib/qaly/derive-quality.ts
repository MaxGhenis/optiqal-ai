/**
 * Derive quality of life effects from mechanism effects
 *
 * This bridges mechanism-level effects to quality-of-life (utility) changes.
 *
 * Quality effects represent day-to-day functioning improvements:
 * - Mobility & physical function
 * - Energy levels & fatigue
 * - Mental health & cognitive function
 * - Pain & discomfort
 * - Sleep & recovery
 *
 * These are distinct from mortality effects - someone can have improved
 * quality of life without extending lifespan, or vice versa.
 */

import type { MechanismEffect, QualityEffect, Distribution } from "./types";

/**
 * Mechanism effect on quality of life (utility delta per unit change)
 *
 * perUnit: utility change per 1 unit change in the mechanism
 * - Positive = increase in mechanism improves quality (protective mechanisms)
 * - Negative = increase in mechanism worsens quality (harmful mechanisms)
 *
 * Values derived from health utility studies and disability weight literature.
 */
const MECHANISM_TO_QUALITY: Record<
  string,
  { perUnit: number; units: string; source: string }
> = {
  // === ADIPOSITY ===
  // Obesity associated with utility decrements of 0.05-0.15 depending on severity
  // Kolotkin 2001, Jia 2005: BMI 35+ associated with ~0.10 utility loss
  // Per % body fat (rough conversion from BMI): ~0.002 per %
  adiposity: {
    perUnit: -0.002,
    units: "% body fat",
    source: "Kolotkin 2001, Jia 2005: Obesity utility decrements 0.05-0.15",
  },

  // === INSULIN SENSITIVITY ===
  // Diabetes associated with utility loss of 0.05-0.10
  // Clarke 2002: Type 2 diabetes utility decrement ~0.07
  // Per % improvement in sensitivity: modest benefit
  insulin_sensitivity: {
    perUnit: 0.0008,
    units: "% improvement",
    source: "Clarke 2002: Diabetes utility decrement ~0.07",
  },

  // === INFLAMMATION ===
  // Chronic inflammation linked to fatigue, pain, depression
  // Fatigue/pain each contribute ~0.05-0.10 utility loss
  // Per % CRP reduction: small but meaningful
  systemic_inflammation: {
    perUnit: -0.0005,
    units: "% CRP increase",
    source: "Fatigue/chronic pain utility studies",
  },

  // === SLEEP QUALITY ===
  // Poor sleep strongly affects quality of life
  // Strine 2005: Sleep disorders utility decrement ~0.08-0.12
  // Per SD improvement: ~0.03
  sleep_quality: {
    perUnit: 0.03,
    units: "SD improvement",
    source: "Strine 2005: Sleep disorders utility decrement 0.08-0.12",
  },

  // === MUSCLE MASS ===
  // Sarcopenia affects mobility and physical function
  // Janssen 2004: Functional impairment utility decrement ~0.05-0.10
  // Per % increase: modest benefit
  muscle_mass: {
    perUnit: 0.001,
    units: "% increase",
    source: "Janssen 2004: Sarcopenia functional impairment",
  },

  // === CARDIORESPIRATORY FITNESS ===
  // Higher fitness = better functional capacity, less dyspnea
  // Sullivan 2006: NYHA class improvements ~0.05 utility per class
  // Per % improvement in cardiac output: ~0.001
  cardiac_output: {
    perUnit: 0.001,
    units: "% improvement",
    source: "Sullivan 2006: Functional capacity utilities",
  },

  // === LUNG FUNCTION ===
  // COPD/respiratory impairment significantly affects QoL
  // Rutten-van Mölken 2006: Severe COPD utility decrement ~0.15-0.20
  // Per % FEV1 improvement: ~0.002
  lung_function: {
    perUnit: 0.002,
    units: "% FEV1 improvement",
    source: "Rutten-van Mölken 2006: COPD utility studies",
  },

  // === BONE DENSITY ===
  // Fractures severely affect quality, but density itself less so
  // Post-fracture utility decrement ~0.20-0.30 (but transient)
  // Indirect effect via fracture prevention: small per %
  bone_density: {
    perUnit: 0.0003,
    units: "% increase",
    source: "Hip fracture utility studies",
  },

  // === STRESS HORMONES ===
  // Chronic stress affects mood, energy, cognition
  // Depression/anxiety utility decrement ~0.10-0.20
  // Per SD increase in cortisol dysregulation: ~0.02 worse
  stress_hormones: {
    perUnit: -0.02,
    units: "SD increase",
    source: "Depression/anxiety utility literature",
  },

  // === BLOOD PRESSURE ===
  // Hypertension itself has minimal QoL impact (often asymptomatic)
  // Main effect is via stroke/heart attack risk (captured in mortality)
  // Small effect from medication side effects avoided
  blood_pressure: {
    perUnit: -0.0002,
    units: "mmHg",
    source: "Hypertension often asymptomatic; minimal direct QoL impact",
  },

  // === LIPIDS ===
  // Dyslipidemia asymptomatic; QoL effect negligible
  lipid_profile: {
    perUnit: 0.0001,
    units: "% LDL change",
    source: "Dyslipidemia asymptomatic; minimal QoL impact",
  },

  // === NEUROPLASTICITY / COGNITIVE FUNCTION ===
  // Cognitive impairment strongly affects QoL
  // Andersen 2004: Mild cognitive impairment ~0.05-0.10 decrement
  // Per SD improvement: ~0.03
  neuroplasticity: {
    perUnit: 0.03,
    units: "SD improvement",
    source: "Andersen 2004: Cognitive impairment utility studies",
  },

  // === BDNF ===
  // Linked to depression, cognitive function
  // Per SD increase: ~0.02 benefit
  bdnf_levels: {
    perUnit: 0.02,
    units: "SD increase",
    source: "Depression/cognitive function pathways",
  },

  // === NEUROTRANSMITTER BALANCE ===
  // Depression/mood strongly affects QoL
  // Revicki 2000: Major depression utility decrement ~0.20-0.30
  // Per SD improvement: ~0.03
  neurotransmitter_balance: {
    perUnit: 0.03,
    units: "SD improvement",
    source: "Revicki 2000: Depression utility decrement 0.20-0.30",
  },

  // === OXIDATIVE STRESS ===
  // Indirect effects via other mechanisms
  oxidative_stress: {
    perUnit: -0.0003,
    units: "% increase",
    source: "Indirect effects via inflammation/aging",
  },

  // === TELOMERE LENGTH ===
  // Biological aging marker; indirect QoL effects
  telomere_length: {
    perUnit: 0.005,
    units: "SD increase",
    source: "Aging/cellular health literature",
  },
};

/**
 * Evidence quality multipliers for uncertainty
 */
const EVIDENCE_SD_MULTIPLIERS: Record<string, number> = {
  strong: 1.0,
  moderate: 1.5,
  weak: 2.0,
};

/**
 * Get the mean value from a distribution
 */
function getDistributionMean(dist: Distribution): number {
  switch (dist.type) {
    case "point":
      return dist.value;
    case "normal":
      return dist.mean;
    case "lognormal":
      return Math.exp(dist.logMean + (dist.logSd * dist.logSd) / 2);
    case "beta":
      return dist.alpha / (dist.alpha + dist.beta);
    case "uniform":
      return (dist.min + dist.max) / 2;
  }
}

/**
 * Get the SD from a distribution
 */
function getDistributionSD(dist: Distribution): number {
  switch (dist.type) {
    case "point":
      return 0;
    case "normal":
      return dist.sd;
    case "lognormal": {
      const variance =
        (Math.exp(dist.logSd * dist.logSd) - 1) *
        Math.exp(2 * dist.logMean + dist.logSd * dist.logSd);
      return Math.sqrt(variance);
    }
    case "beta": {
      const a = dist.alpha;
      const b = dist.beta;
      return Math.sqrt((a * b) / ((a + b) ** 2 * (a + b + 1)));
    }
    case "uniform":
      return (dist.max - dist.min) / Math.sqrt(12);
  }
}

/**
 * Convert a mechanism effect to a quality (utility) delta
 *
 * Logic:
 * - perUnit defines how mechanism changes affect utility
 * - direction tells us whether the mechanism is increasing or decreasing
 * - The effective change is: +effectMean for increase, -effectMean for decrease
 * - utilityDelta = perUnit * effectiveChange
 *
 * Example (adiposity, perUnit = -0.002):
 * - decrease by 15%: delta = -0.002 * (-15) = +0.03 (quality improves ✓)
 * - increase by 15%: delta = -0.002 * (+15) = -0.03 (quality worsens ✓)
 *
 * Example (sleep_quality, perUnit = +0.03):
 * - increase by 0.5 SD: delta = 0.03 * (+0.5) = +0.015 (quality improves ✓)
 * - decrease by 0.5 SD: delta = 0.03 * (-0.5) = -0.015 (quality worsens ✓)
 */
function mechanismToQualityDelta(effect: MechanismEffect): {
  delta: number;
  sd: number;
} {
  const conversion = MECHANISM_TO_QUALITY[effect.mechanism];
  const effectMean = getDistributionMean(effect.effectSize);
  const effectSD = getDistributionSD(effect.effectSize);
  const sdMultiplier = EVIDENCE_SD_MULTIPLIERS[effect.evidenceQuality] || 1.5;

  // Effective change: positive for increase, negative for decrease
  const effectiveChange =
    effect.direction === "increase" ? effectMean : -effectMean;

  if (!conversion) {
    // Unknown mechanism - use conservative default
    // Assume tiny benefit per unit increase with high uncertainty
    const defaultPerUnit = 0.0005;
    return {
      delta: defaultPerUnit * effectiveChange,
      sd: Math.abs(effectSD * 0.001 * sdMultiplier) + 0.005,
    };
  }

  const delta = conversion.perUnit * effectiveChange;
  const sd =
    Math.abs(effectSD * Math.abs(conversion.perUnit) * sdMultiplier) + 0.002;

  return { delta, sd };
}

/**
 * Derive a quality effect from mechanism effects
 *
 * Aggregates mechanism → utility conversions into a combined
 * normal distribution for overall quality of life change.
 *
 * Returns a QualityEffect with the combined utility change in
 * the subjectiveWellbeing field (the simulation uses this).
 */
export function deriveQualityFromMechanisms(
  mechanisms: MechanismEffect[]
): QualityEffect | null {
  if (mechanisms.length === 0) {
    return null;
  }

  // Convert each mechanism to utility delta
  const deltas = mechanisms.map((m) => mechanismToQualityDelta(m));

  // Combine effects (assuming independence, sum deltas)
  const combinedMean = deltas.reduce((sum, { delta }) => sum + delta, 0);

  // Combined SD: sqrt of sum of variances
  const combinedSD = Math.sqrt(
    deltas.reduce((sum, { sd }) => sum + sd * sd, 0)
  );

  // If the combined effect is essentially zero, return null
  if (Math.abs(combinedMean) < 0.001 && combinedSD < 0.005) {
    return null;
  }

  // Return in the QualityEffect format expected by the simulation
  return {
    conditionEffects: [],
    directDimensionEffects: [],
    subjectiveWellbeing: {
      type: "normal",
      mean: combinedMean,
      sd: Math.max(combinedSD, 0.005), // minimum uncertainty
    },
    onsetDelay: 0,
    persistenceAfterStopping: undefined,
    decayRate: 0,
  };
}

/**
 * Per-mechanism contribution to quality effect
 */
export interface MechanismQualityBreakdown {
  mechanism: string;
  utilityDelta: number;
  sd: number;
  causalFraction: number;
  source?: string;
}

/**
 * Quality effect with per-mechanism breakdown for transparency
 */
export interface QualityWithBreakdown {
  combined: QualityEffect;
  breakdown: MechanismQualityBreakdown[];
}

/**
 * Get causal fraction based on evidence quality
 */
function getEvidenceCausalFraction(quality: string): number {
  switch (quality) {
    case "strong":
      return 0.8; // RCT-level evidence
    case "moderate":
      return 0.5; // Cohort studies
    case "weak":
    default:
      return 0.2; // Observational/cross-sectional
  }
}

/**
 * Derive quality effect with per-mechanism breakdown
 *
 * Returns both the combined effect and individual mechanism contributions
 * for transparency and Monte Carlo uncertainty visualization.
 */
export function deriveQualityWithBreakdown(
  mechanisms: MechanismEffect[]
): QualityWithBreakdown | null {
  if (mechanisms.length === 0) {
    return null;
  }

  const breakdown: MechanismQualityBreakdown[] = mechanisms.map((m) => {
    const { delta, sd } = mechanismToQualityDelta(m);
    const conversion = MECHANISM_TO_QUALITY[m.mechanism];
    return {
      mechanism: m.mechanism,
      utilityDelta: delta,
      sd,
      causalFraction: getEvidenceCausalFraction(m.evidenceQuality),
      source: conversion?.source,
    };
  });

  // Combine effects (assuming independence, sum deltas)
  const combinedMean = breakdown.reduce((sum, b) => sum + b.utilityDelta, 0);

  // Combined SD: sqrt of sum of variances
  const combinedSD = Math.sqrt(
    breakdown.reduce((sum, b) => sum + b.sd * b.sd, 0)
  );

  // If the combined effect is essentially zero, return null
  if (Math.abs(combinedMean) < 0.001 && combinedSD < 0.005) {
    return null;
  }

  return {
    combined: {
      conditionEffects: [],
      directDimensionEffects: [],
      subjectiveWellbeing: {
        type: "normal",
        mean: combinedMean,
        sd: Math.max(combinedSD, 0.005),
      },
      onsetDelay: 0,
      persistenceAfterStopping: undefined,
      decayRate: 0,
    },
    breakdown,
  };
}
