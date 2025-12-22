/**
 * Calibrated Confounding Adjustment Module
 *
 * Calibrated against actual RCT vs observational discrepancies from literature.
 *
 * Key calibration sources:
 * - Ballin 2021: Exercise RCTs show no mortality effect vs HR 0.50-0.66 observational
 * - Finnish Twin Cohort 2024: Identical twins discordant for PA show no mortality diff
 * - Statin meta-analysis: HR 0.54 (observational) vs 0.84 (RCT)
 * - PREDIMED: Mediterranean diet RCT shows ~70% of observational effect
 * - IHME Burden of Proof: Conservative interpretation using between-study heterogeneity
 */

import type { Distribution } from "./types";

/**
 * Calibration data point from literature
 */
export interface CalibrationPoint {
  intervention: string;
  category: string;
  observationalHR: number;
  rctHR: number | null; // null if no RCT evidence
  impliedCausalFraction: number | null;
  source: string;
  year: number;
  notes: string;
}

/**
 * Calibration dataset from RCT vs observational comparisons
 */
export const CALIBRATION_DATA: CalibrationPoint[] = [
  // EXERCISE
  {
    intervention: "Physical activity (general)",
    category: "exercise",
    observationalHR: 0.58, // Average of 0.50-0.66 from harmonized meta-analysis
    rctHR: 1.0, // Ballin 2021: "does not reduce all-cause mortality"
    impliedCausalFraction: 0.0, // If RCT shows HR=1, causal fraction is 0
    source: "Ballin et al. 2021, J Intern Med; Moholdt et al. 2024",
    year: 2021,
    notes:
      "Critical review of RCTs (~50k participants) shows exercise does not reduce mortality. " +
      "Observational HR likely entirely due to healthy user bias and reverse causation.",
  },
  {
    intervention: "Physical activity (twin discordant)",
    category: "exercise",
    observationalHR: 0.58,
    rctHR: 1.0, // Twins show no difference
    impliedCausalFraction: 0.0,
    source: "Finnish Twin Cohort 2024; Karvinen et al.",
    year: 2024,
    notes:
      "Identical twins discordant for PA show no mortality difference. " +
      "Genetic confounding accounts for observational association.",
  },
  {
    intervention: "Walking 30 min/day",
    category: "exercise",
    observationalHR: 0.84, // From our precomputed
    rctHR: null, // No walking-specific RCT
    impliedCausalFraction: 0.15, // Conservative given general exercise findings
    source: "Estimate based on exercise calibration",
    year: 2024,
    notes:
      "Walking may have higher causal fraction than vigorous exercise " +
      "(less reverse causation), but still apply skeptical prior.",
  },

  // DIET
  {
    intervention: "Mediterranean diet",
    category: "diet",
    observationalHR: 0.77, // 23% reduction from meta-analysis
    rctHR: 0.70, // PREDIMED: 30% CVD reduction (using as proxy)
    impliedCausalFraction: 0.75, // log(0.70)/log(0.77) ≈ 1.37, cap at reasonable
    source: "PREDIMED Trial 2018; Meta-analysis 2024",
    year: 2018,
    notes:
      "PREDIMED RCT confirms substantial causal effect. " +
      "Observational slightly overestimates but direction confirmed.",
  },
  {
    intervention: "Nut consumption",
    category: "diet",
    observationalHR: 0.80, // From whatnut analysis
    rctHR: 0.70, // PREDIMED nuts arm
    impliedCausalFraction: 0.55, // Moderate - some healthy user bias
    source: "Aune et al. 2016; PREDIMED 2013",
    year: 2016,
    notes:
      "Nuts have RCT evidence from PREDIMED. " +
      "Some confounding but substantial causal effect likely.",
  },

  // MEDICAL
  {
    intervention: "Statins",
    category: "medical",
    observationalHR: 0.54,
    rctHR: 0.84,
    impliedCausalFraction: 0.28, // log(0.84)/log(0.54) = 0.17/0.62 = 0.28
    source: "Danaei et al. 2012; RCT meta-analysis",
    year: 2012,
    notes:
      "Classic example of healthy user bias in observational studies. " +
      "Even with randomization, only 28% of observational effect is causal.",
  },
  {
    intervention: "Aspirin (CVD prevention)",
    category: "medical",
    observationalHR: 0.70,
    rctHR: 0.90, // More recent RCTs show smaller effect
    impliedCausalFraction: 0.30,
    source: "ARRIVE, ASPREE trials",
    year: 2018,
    notes:
      "Recent RCTs show aspirin less beneficial than observational suggested.",
  },

  // SLEEP
  {
    intervention: "Sleep duration (7-8h)",
    category: "sleep",
    observationalHR: 0.85,
    rctHR: null,
    impliedCausalFraction: 0.30, // Conservative - substantial reverse causation
    source: "Cappuccio et al. 2010; No mortality RCTs",
    year: 2010,
    notes:
      "No RCT evidence for sleep and mortality. " +
      "Substantial reverse causation (sick people sleep more/less).",
  },

  // SUBSTANCE
  {
    intervention: "Smoking cessation",
    category: "substance",
    observationalHR: 0.60,
    rctHR: 0.75, // RCT meta-analysis
    impliedCausalFraction: 0.56, // log(0.75)/log(0.60) = 0.29/0.51 = 0.56
    source: "Taylor et al. 2014",
    year: 2014,
    notes:
      "Smoking cessation has strong causal effect confirmed by RCTs. " +
      "Some selection bias but majority is causal.",
  },
  {
    intervention: "Moderate alcohol (J-curve)",
    category: "substance",
    observationalHR: 0.85, // Apparent protective effect
    rctHR: 1.0, // MR studies show no benefit
    impliedCausalFraction: 0.0,
    source: "Stockwell et al. 2016; MR studies",
    year: 2016,
    notes:
      "The alcohol J-curve is likely entirely confounded. " +
      "MR studies show no protective effect of moderate drinking.",
  },
];

/**
 * Calibrated Beta priors for causal fraction by category
 *
 * These are derived from the calibration data above using:
 * - Mean causal fraction from RCT/observational comparisons
 * - Wide uncertainty to reflect limited calibration data
 *
 * Beta(α, β) where mean = α/(α+β)
 */
export const CALIBRATED_PRIORS: Record<
  string,
  {
    alpha: number;
    beta: number;
    mean: number;
    ci95: { low: number; high: number };
    rationale: string;
    calibrationSources: string[];
  }
> = {
  // EXERCISE: Very skeptical prior - RCTs and twin studies show ~0 causal effect
  exercise: {
    alpha: 1.2,
    beta: 6.0,
    mean: 0.17, // Was 0.33, now much more skeptical
    ci95: { low: 0.02, high: 0.45 },
    rationale:
      "Ballin 2021 critical review: RCTs show no mortality effect. " +
      "Finnish Twin Cohort 2024: identical twins show no difference. " +
      "Observational HR 0.50-0.66 likely entirely due to healthy user bias.",
    calibrationSources: [
      "Ballin et al. 2021 (RCT review, n=50k)",
      "Finnish Twin Cohort 2024",
      "Mendelian randomization studies",
    ],
  },

  // DIET: Less skeptical - PREDIMED confirms causal effect
  diet: {
    alpha: 3.0,
    beta: 3.0,
    mean: 0.50, // Was 0.33, now more generous
    ci95: { low: 0.15, high: 0.85 },
    rationale:
      "PREDIMED RCT confirms substantial causal effect of Mediterranean diet. " +
      "Nuts, olive oil have RCT backing. Still some healthy user bias.",
    calibrationSources: [
      "PREDIMED Trial 2018 (RCT, n=7447)",
      "Aune et al. 2016 (nut meta-analysis)",
    ],
  },

  // SLEEP: Skeptical - no RCT evidence, reverse causation
  sleep: {
    alpha: 1.5,
    beta: 4.5,
    mean: 0.25,
    ci95: { low: 0.03, high: 0.58 },
    rationale:
      "No RCTs for sleep and mortality. High reverse causation risk: " +
      "illness affects sleep duration. CBT-I shows causal quality effects.",
    calibrationSources: [
      "Cappuccio et al. 2010 (cohort)",
      "No mortality RCTs available",
    ],
  },

  // STRESS: Very skeptical
  stress: {
    alpha: 1.2,
    beta: 5.0,
    mean: 0.19,
    ci95: { low: 0.02, high: 0.50 },
    rationale:
      "Meditation/mindfulness RCTs show much smaller effects than observational. " +
      "Stress levels heavily confounded with SES, health behaviors.",
    calibrationSources: [
      "Goyal et al. 2014 (meditation meta-analysis)",
      "Khoury et al. 2015",
    ],
  },

  // SUBSTANCE: Moderate - some RCT evidence
  substance: {
    alpha: 2.0,
    beta: 4.0,
    mean: 0.33,
    ci95: { low: 0.06, high: 0.68 },
    rationale:
      "Smoking cessation has strong RCT backing (causal fraction ~56%). " +
      "Alcohol J-curve is entirely confounded (causal fraction ~0%). " +
      "Average is moderate.",
    calibrationSources: [
      "Taylor et al. 2014 (smoking cessation RCTs)",
      "Stockwell et al. 2016 (alcohol bias)",
    ],
  },

  // MEDICAL: Less skeptical - usually RCT-based
  medical: {
    alpha: 2.5,
    beta: 4.0,
    mean: 0.38, // Was 0.57, now more skeptical based on statin example
    ci95: { low: 0.08, high: 0.73 },
    rationale:
      "Medical interventions have RCT evidence but still show observational inflation. " +
      "Statins: observational HR 0.54 vs RCT HR 0.84 (causal fraction ~28%).",
    calibrationSources: [
      "Danaei et al. 2012 (statin bias)",
      "ARRIVE/ASPREE (aspirin RCTs)",
    ],
  },

  // SOCIAL: Very skeptical
  social: {
    alpha: 1.0,
    beta: 5.5,
    mean: 0.15,
    ci95: { low: 0.01, high: 0.42 },
    rationale:
      "Social relationships heavily confounded with SES, mental health, " +
      "physical health. No RCT evidence possible for mortality.",
    calibrationSources: ["Holt-Lunstad et al. 2010 (observational only)"],
  },

  // OTHER: Conservative
  other: {
    alpha: 1.2,
    beta: 4.8,
    mean: 0.20,
    ci95: { low: 0.02, high: 0.50 },
    rationale:
      "Unknown intervention type. Using conservative prior " +
      "reflecting general observational bias.",
    calibrationSources: [],
  },
};

/**
 * Intervention-specific calibrated priors
 *
 * For interventions with direct RCT evidence, use intervention-specific prior
 * instead of category default.
 */
export const INTERVENTION_SPECIFIC_PRIORS: Record<
  string,
  {
    alpha: number;
    beta: number;
    mean: number;
    rationale: string;
    source: string;
  }
> = {
  walking_30min_daily: {
    alpha: 1.5,
    beta: 6.0,
    mean: 0.20,
    rationale:
      "Walking has less reverse causation than vigorous exercise (sick people can still walk), " +
      "but still subject to healthy user bias. No walking-specific mortality RCT.",
    source: "Extrapolated from general exercise calibration",
  },

  mediterranean_diet: {
    alpha: 4.0,
    beta: 2.5,
    mean: 0.62,
    rationale:
      "PREDIMED RCT confirms strong causal effect on CVD. " +
      "Extrapolating to mortality with modest skepticism.",
    source: "PREDIMED 2018",
  },

  nut_consumption: {
    alpha: 3.0,
    beta: 3.0,
    mean: 0.50,
    rationale:
      "PREDIMED nuts arm shows causal CVD benefit. " +
      "Whatnut analysis suggests ~50% causal fraction for mortality.",
    source: "PREDIMED 2013; Ghenis 2025",
  },

  smoking_cessation: {
    alpha: 4.0,
    beta: 3.0,
    mean: 0.57,
    rationale:
      "Strong RCT evidence for smoking cessation and mortality. " +
      "Causal fraction ~56% from Taylor et al. meta-analysis.",
    source: "Taylor et al. 2014",
  },

  statin_therapy: {
    alpha: 2.0,
    beta: 5.0,
    mean: 0.29,
    rationale:
      "Well-documented case of observational inflation. " +
      "HR 0.54 observational vs 0.84 RCT → causal fraction ~28%.",
    source: "Danaei et al. 2012",
  },

  moderate_alcohol: {
    alpha: 1.0,
    beta: 9.0,
    mean: 0.10,
    rationale:
      "J-curve likely entirely confounded. MR studies show no benefit. " +
      "Small residual for possible antioxidant effects in wine.",
    source: "Stockwell et al. 2016; MR studies",
  },
};

/**
 * Get calibrated prior for an intervention
 *
 * Uses intervention-specific prior if available, otherwise category default.
 */
export function getCalibratedPrior(
  interventionId: string,
  category: string
): {
  alpha: number;
  beta: number;
  mean: number;
  rationale: string;
  sources: string[];
} {
  // Check for intervention-specific prior
  if (interventionId in INTERVENTION_SPECIFIC_PRIORS) {
    const specific = INTERVENTION_SPECIFIC_PRIORS[interventionId];
    return {
      alpha: specific.alpha,
      beta: specific.beta,
      mean: specific.mean,
      rationale: specific.rationale,
      sources: [specific.source],
    };
  }

  // Fall back to category prior
  const categoryPrior = CALIBRATED_PRIORS[category] || CALIBRATED_PRIORS.other;
  return {
    alpha: categoryPrior.alpha,
    beta: categoryPrior.beta,
    mean: categoryPrior.mean,
    rationale: categoryPrior.rationale,
    sources: categoryPrior.calibrationSources,
  };
}

/**
 * Compare old vs new priors for transparency
 */
export const PRIOR_COMPARISON = {
  exercise: {
    old: { alpha: 2.5, beta: 5.0, mean: 0.33 },
    new: { alpha: 1.2, beta: 6.0, mean: 0.17 },
    change: "More skeptical (-48%)",
    reason: "RCTs and twin studies show ~0 causal effect",
  },
  diet: {
    old: { alpha: 2.0, beta: 4.0, mean: 0.33 },
    new: { alpha: 3.0, beta: 3.0, mean: 0.50 },
    change: "More generous (+52%)",
    reason: "PREDIMED RCT confirms causal effect",
  },
  medical: {
    old: { alpha: 4.0, beta: 3.0, mean: 0.57 },
    new: { alpha: 2.5, beta: 4.0, mean: 0.38 },
    change: "More skeptical (-33%)",
    reason: "Statin observational vs RCT discrepancy",
  },
};
