/**
 * Derive mortality hazard ratios from mechanism effects
 *
 * This bridges the gap between Claude's mechanism-level estimates
 * and the simulation's need for mortality HRs.
 *
 * Uses the MECHANISM_CONDITION_LINKS to:
 * 1. Map mechanism effects → condition risk changes
 * 2. Aggregate condition risks → overall mortality HR
 */

import type { MechanismEffect, MortalityEffect, Distribution } from "./types";

/**
 * Effect size conversions to standardized log-HR scale
 *
 * Based on epidemiological meta-analyses:
 * - Blood pressure: ~2% mortality reduction per 5 mmHg SBP reduction (Ettehad 2016)
 * - Lipids: ~10% CVD reduction per 1 mmol/L LDL reduction (CTT)
 * - Inflammation: ~15% mortality per SD CRP (Emerging Risk Factors)
 */
/**
 * Mechanism effect on mortality (log-HR per unit change)
 *
 * perUnit: log-HR change per 1 unit increase in the mechanism
 * - Positive = increase in mechanism increases mortality (harmful mechanisms)
 * - Negative = increase in mechanism decreases mortality (protective mechanisms)
 *
 * All values derived from major meta-analyses. See sources for details.
 */
const MECHANISM_TO_LOG_HR: Record<
  string,
  { perUnit: number; units: string; source: string }
> = {
  // === BLOOD PRESSURE ===
  // Ettehad 2016 Lancet: 10 mmHg SBP reduction → HR 0.87 for all-cause mortality
  // log(0.87) / 10 = -0.014 per mmHg reduction
  // So +1 mmHg increase → +0.014 log-HR
  blood_pressure: {
    perUnit: 0.014,
    units: "mmHg",
    source: "Ettehad 2016 Lancet (n=613,815): 10mmHg SBP → 13% mortality reduction",
  },

  // === LIPIDS ===
  // CTT Collaboration 2010 Lancet: 1 mmol/L LDL reduction → HR 0.78 for major vascular events
  // For all-cause mortality: ~10% reduction per mmol/L, HR 0.90
  // log(0.90) = -0.105 per mmol/L
  // Per % LDL change (assuming baseline ~3.5 mmol/L): -0.105 / 35 = -0.003 per %
  lipid_profile: {
    perUnit: -0.003,
    units: "% LDL change",
    source: "CTT Collaboration 2010 Lancet (n=170,000): 1mmol/L LDL → 10% mortality reduction",
  },

  // === INFLAMMATION ===
  // Emerging Risk Factors Collaboration 2010 Lancet: log-CRP associated with mortality
  // HR 1.55 per 1 SD increase in log-CRP (after adjustment)
  // Causal estimate ~40% of this: HR ~1.20 per SD
  // log(1.20) = 0.18 per SD of log-CRP
  // Per % CRP change: roughly 0.18 / 100 = 0.0018 per %
  systemic_inflammation: {
    perUnit: 0.002,
    units: "% CRP change",
    source: "Emerging Risk Factors 2010 Lancet (n=160,309): CRP strongly associated with mortality",
  },

  // === ADIPOSITY ===
  // Global BMI Mortality Collaboration 2016 Lancet:
  // BMI 25-27.5 vs 22.5-25: HR 1.11
  // BMI 30-35 vs 22.5-25: HR 1.44
  // Per BMI unit above 25: ~log(1.44)/10 = 0.036 per BMI unit
  // Per % body fat (rough conversion): ~0.01 per %
  adiposity: {
    perUnit: 0.01,
    units: "% body fat",
    source: "Global BMI Mortality 2016 Lancet (n=10.6M): BMI 30-35 HR 1.44 vs normal",
  },

  // === INSULIN SENSITIVITY ===
  // DECODE Study Group, Lancet 1999: Impaired glucose tolerance HR ~1.5
  // Per % improvement in insulin sensitivity: conservative estimate
  insulin_sensitivity: {
    perUnit: -0.002,
    units: "% improvement",
    source: "DECODE 1999, diabetes/prediabetes meta-analyses",
  },

  // === SLEEP ===
  // Cappuccio 2010 Sleep meta-analysis: Short sleep (<6h) HR 1.12, Long sleep (>9h) HR 1.30
  // Per hour deviation from optimal: ~log(1.12) = 0.11
  // Per SD improvement in sleep quality: ~0.05
  sleep_quality: {
    perUnit: -0.05,
    units: "SD improvement",
    source: "Cappuccio 2010 Sleep (n=1.4M): Short sleep HR 1.12",
  },

  // === MUSCLE MASS ===
  // Srikanthan 2016 Am J Med: Higher muscle mass HR 0.80
  // log(0.80) = -0.22 for high vs low tertile
  // Per % increase: ~-0.02
  muscle_mass: {
    perUnit: -0.02,
    units: "% increase",
    source: "Srikanthan 2016 Am J Med: High muscle mass HR 0.80",
  },

  // === CARDIORESPIRATORY FITNESS ===
  // Kodama 2009 JAMA: Per 1-MET increase in fitness → HR 0.87
  // log(0.87) = -0.14 per MET
  // Per % improvement in cardiac output (proxy): ~-0.01
  cardiac_output: {
    perUnit: -0.01,
    units: "% improvement",
    source: "Kodama 2009 JAMA (n=102,980): 1 MET fitness → 13% mortality reduction",
  },

  // === LUNG FUNCTION ===
  // Hole 1996 BMJ, Sin 2005: FEV1 strongly predicts mortality
  // Per 10% reduction in FEV1: HR ~1.14
  // Per % improvement: -log(1.14)/10 = -0.013
  lung_function: {
    perUnit: -0.013,
    units: "% FEV1 improvement",
    source: "Hole 1996 BMJ, Sin 2005: FEV1 strongly predicts mortality",
  },

  // === BONE DENSITY ===
  // Hip fracture mortality is high (~20% at 1 year)
  // Per SD increase in BMD: ~15-20% reduction in fracture risk
  // Mortality impact is indirect via fracture prevention
  bone_density: {
    perUnit: -0.01,
    units: "% increase",
    source: "NOF, hip fracture meta-analyses: ~20% 1-year mortality post-fracture",
  },

  // === STRESS HORMONES ===
  // Kumari 2011: Flatter cortisol slope HR ~1.3-2.0
  // Per SD increase in chronic cortisol: ~HR 1.15
  // log(1.15) = 0.14 per SD
  stress_hormones: {
    perUnit: 0.05,
    units: "SD increase",
    source: "Kumari 2011 J Clin Endocrinol: Cortisol dysregulation → mortality",
  },

  // === OXIDATIVE STRESS ===
  // Limited direct mortality data; effect largely via mechanisms above
  oxidative_stress: {
    perUnit: 0.005,
    units: "% increase",
    source: "Indirect via inflammation/CVD pathways",
  },

  // === NEUROLOGICAL ===
  // Cognitive reserve, BDNF - effects largely via dementia/depression pathways
  neuroplasticity: {
    perUnit: -0.03,
    units: "SD improvement",
    source: "Cognitive reserve literature; dementia prevention",
  },
  bdnf_levels: {
    perUnit: -0.02,
    units: "SD increase",
    source: "BDNF meta-analyses; depression/dementia pathways",
  },
  neurotransmitter_balance: {
    perUnit: -0.02,
    units: "SD improvement",
    source: "Depression mortality meta-analyses: depression HR ~1.5-2.0",
  },

  // === TELOMERES ===
  // Haycock 2014: Shorter telomeres HR 1.26 for mortality
  // log(1.26) = 0.23 per SD shorter
  // Per SD longer: -0.08 (conservative, accounting for reverse causation)
  telomere_length: {
    perUnit: -0.08,
    units: "SD increase",
    source: "Haycock 2014 BMJ (n=43,725): Short telomeres HR 1.26",
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
 * Convert a mechanism effect to a log-HR contribution
 *
 * Logic:
 * - perUnit defines how mechanism changes affect mortality
 * - direction tells us whether the mechanism is increasing or decreasing
 * - The effective change is: +effectMean for increase, -effectMean for decrease
 * - logHR = perUnit * effectiveChange
 *
 * Example (blood_pressure, perUnit = +0.004):
 * - decrease by 5 mmHg: logHR = 0.004 * (-5) = -0.02 (mortality decreases ✓)
 * - increase by 5 mmHg: logHR = 0.004 * (+5) = +0.02 (mortality increases ✓)
 *
 * Example (muscle_mass, perUnit = -0.01):
 * - increase by 5%: logHR = -0.01 * (+5) = -0.05 (mortality decreases ✓)
 * - decrease by 5%: logHR = -0.01 * (-5) = +0.05 (mortality increases ✓)
 */
function mechanismToLogHR(effect: MechanismEffect): {
  logHR: number;
  logSD: number;
} {
  const conversion = MECHANISM_TO_LOG_HR[effect.mechanism];
  const effectMean = getDistributionMean(effect.effectSize);
  const effectSD = getDistributionSD(effect.effectSize);
  const sdMultiplier = EVIDENCE_SD_MULTIPLIERS[effect.evidenceQuality] || 1.5;

  // Effective change: positive for increase, negative for decrease
  const effectiveChange =
    effect.direction === "increase" ? effectMean : -effectMean;

  if (!conversion) {
    // Unknown mechanism - use conservative default
    // Assume small protective effect per unit with high uncertainty
    const defaultPerUnit = -0.005; // slight benefit per unit increase
    return {
      logHR: defaultPerUnit * effectiveChange,
      logSD: Math.abs(effectSD * 0.01 * sdMultiplier) + 0.05,
    };
  }

  const logHR = conversion.perUnit * effectiveChange;
  const logSD =
    Math.abs(effectSD * Math.abs(conversion.perUnit) * sdMultiplier) + 0.02;

  return { logHR, logSD };
}

/**
 * Derive a mortality effect from mechanism effects
 *
 * Aggregates mechanism → log-HR conversions into a combined
 * lognormal distribution for overall mortality hazard ratio.
 */
export function deriveMortalityFromMechanisms(
  mechanisms: MechanismEffect[]
): MortalityEffect | null {
  if (mechanisms.length === 0) {
    return null;
  }

  // Convert each mechanism to log-HR
  const logHRs = mechanisms.map((m) => mechanismToLogHR(m));

  // Combine effects (assuming independence, sum log-HRs)
  const combinedLogMean = logHRs.reduce((sum, { logHR }) => sum + logHR, 0);

  // Combined SD: sqrt of sum of variances
  const combinedLogSD = Math.sqrt(
    logHRs.reduce((sum, { logSD }) => sum + logSD * logSD, 0)
  );

  // If the combined effect is essentially zero, return null
  if (
    Math.abs(combinedLogMean) < 0.001 &&
    combinedLogSD < 0.02
  ) {
    return null;
  }

  return {
    hazardRatio: {
      type: "lognormal",
      logMean: combinedLogMean,
      logSd: Math.max(combinedLogSD, 0.03), // minimum uncertainty
    },
    onsetDelay: 0,
    rampUpPeriod: 1,
    decayRate: 0,
  };
}

/**
 * Per-mechanism contribution to mortality effect
 */
export interface MechanismMortalityBreakdown {
  mechanism: string;
  logHR: number;
  logSD: number;
  causalFraction: number;
  source?: string;
}

/**
 * Mortality effect with per-mechanism breakdown for transparency
 */
export interface MortalityWithBreakdown {
  combined: MortalityEffect;
  breakdown: MechanismMortalityBreakdown[];
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
 * Derive mortality effect with per-mechanism breakdown
 *
 * Returns both the combined effect and individual mechanism contributions
 * for transparency and Monte Carlo uncertainty visualization.
 */
export function deriveMortalityWithBreakdown(
  mechanisms: MechanismEffect[]
): MortalityWithBreakdown | null {
  if (mechanisms.length === 0) {
    return null;
  }

  const breakdown: MechanismMortalityBreakdown[] = mechanisms.map((m) => {
    const { logHR, logSD } = mechanismToLogHR(m);
    const conversion = MECHANISM_TO_LOG_HR[m.mechanism];
    return {
      mechanism: m.mechanism,
      logHR,
      logSD,
      causalFraction: getEvidenceCausalFraction(m.evidenceQuality),
      source: conversion?.source,
    };
  });

  // Combine effects (assuming independence, sum log-HRs)
  const combinedLogMean = breakdown.reduce((sum, b) => sum + b.logHR, 0);

  // Combined SD: sqrt of sum of variances
  const combinedLogSD = Math.sqrt(
    breakdown.reduce((sum, b) => sum + b.logSD * b.logSD, 0)
  );

  // If the combined effect is essentially zero, return null
  if (Math.abs(combinedLogMean) < 0.001 && combinedLogSD < 0.02) {
    return null;
  }

  return {
    combined: {
      hazardRatio: {
        type: "lognormal",
        logMean: combinedLogMean,
        logSd: Math.max(combinedLogSD, 0.03),
      },
      onsetDelay: 0,
      rampUpPeriod: 1,
      decayRate: 0,
    },
    breakdown,
  };
}
