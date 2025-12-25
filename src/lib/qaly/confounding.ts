/**
 * Confounding Adjustment Module
 *
 * Applies evidence-calibrated causal fraction adjustments to intervention effects.
 * Based on methodology from Ghenis (2025) "What Nut?" QALY analysis.
 *
 * Key concepts:
 * - Observational studies overestimate effects due to healthy user bias
 * - We model the "causal fraction" - what proportion of observed effect is causal
 * - Different evidence types and intervention categories have different priors
 * - E-values quantify robustness to unmeasured confounding
 */

import type { Distribution } from "./types";
import { random } from "./random";

/**
 * Configuration for confounding adjustment
 */
export interface ConfoundingConfig {
  /** Beta prior for causal fraction: proportion of observed effect that's causal */
  causalFraction: {
    alpha: number;
    beta: number;
  };

  /** Rationale for this prior */
  rationale: string;

  /** Key calibration sources */
  calibrationSources: string[];
}

/**
 * Category-specific confounding priors
 *
 * CALIBRATED against actual RCT vs observational discrepancies:
 * - Exercise: Ballin 2021 RCT review shows ~0 causal effect, Finnish Twin Cohort confirms
 * - Diet: PREDIMED RCT confirms substantial causal effect (~70% of observational)
 * - Medical: Statin studies show ~28% causal fraction (HR 0.54 obs vs 0.84 RCT)
 *
 * Priors are Beta(α, β) distributions for the causal fraction [0,1].
 * Mean = α/(α+β), with lower values indicating more confounding.
 */
export const CONFOUNDING_BY_CATEGORY: Record<string, ConfoundingConfig> = {
  // Exercise: VERY skeptical - RCTs and twin studies show ~0 causal effect
  // Ballin 2021: "exercise does not reduce all-cause mortality" (n=50k RCT participants)
  // Finnish Twin Cohort 2024: identical twins discordant for PA show no mortality difference
  exercise: {
    causalFraction: { alpha: 1.2, beta: 6.0 },
    rationale:
      "CALIBRATED: RCTs show exercise does not reduce mortality (Ballin 2021, n=50k). " +
      "Twin studies confirm: identical twins discordant for PA show no mortality difference. " +
      "Observational HR 0.50-0.66 likely entirely due to healthy user bias. " +
      "Beta(1.2, 6.0) → mean 17%, 95% CI: 2-45%",
    calibrationSources: [
      "Ballin et al. 2021 (RCT critical review, n=50k)",
      "Finnish Twin Cohort 2024 (twin discordance)",
      "Mendelian randomization studies (null for mortality)",
    ],
  },

  // Diet: Less skeptical - PREDIMED RCT confirms substantial causal effect
  diet: {
    causalFraction: { alpha: 3.0, beta: 3.0 },
    rationale:
      "CALIBRATED: PREDIMED RCT confirms 30% CVD reduction, consistent with observational. " +
      "Nuts, olive oil have RCT backing. Diet has higher causal fraction than exercise. " +
      "Beta(3.0, 3.0) → mean 50%, 95% CI: 15-85%",
    calibrationSources: [
      "PREDIMED Trial 2018 (RCT, n=7447, 30% CVD reduction)",
      "Aune et al. 2016 (nut meta-analysis)",
    ],
  },

  // Sleep: Skeptical - no RCT evidence for mortality, high reverse causation
  sleep: {
    causalFraction: { alpha: 1.5, beta: 4.5 },
    rationale:
      "No RCTs for sleep duration and mortality. High reverse causation risk: " +
      "illness affects sleep patterns. CBT-I shows causal quality-of-life effects. " +
      "Beta(1.5, 4.5) → mean 25%, 95% CI: 3-58%",
    calibrationSources: [
      "Cappuccio et al. 2010 (observational only)",
      "No mortality RCTs available",
    ],
  },

  // Stress: Very skeptical - RCTs show smaller effects
  stress: {
    causalFraction: { alpha: 1.2, beta: 5.0 },
    rationale:
      "Meditation/mindfulness RCTs show much smaller effects than observational. " +
      "Stress levels heavily confounded with SES, health behaviors. " +
      "Beta(1.2, 5.0) → mean 19%, 95% CI: 2-50%",
    calibrationSources: [
      "Goyal et al. 2014 (meditation RCT meta-analysis)",
      "Khoury et al. 2015 (mindfulness-based therapy)",
    ],
  },

  // Substance: Mixed - smoking has RCT backing, alcohol J-curve is confounded
  substance: {
    causalFraction: { alpha: 2.0, beta: 4.0 },
    rationale:
      "CALIBRATED: Smoking cessation has strong RCT backing (causal fraction ~56%). " +
      "Alcohol J-curve is entirely confounded (MR shows no benefit). " +
      "Beta(2.0, 4.0) → mean 33%, 95% CI: 6-68%",
    calibrationSources: [
      "Taylor et al. 2014 (smoking cessation RCT meta, ~56% causal)",
      "Stockwell et al. 2016 (alcohol J-curve is bias)",
      "MR studies (alcohol shows no protective effect)",
    ],
  },

  // Medical: Moderate skepticism - even RCT-based drugs show observational inflation
  // Statins: HR 0.54 observational vs 0.84 RCT → only 28% causal
  medical: {
    causalFraction: { alpha: 2.5, beta: 4.0 },
    rationale:
      "CALIBRATED: Even RCT-based drugs show observational inflation. " +
      "Statins: HR 0.54 observational vs 0.84 RCT (causal fraction ~28%). " +
      "Aspirin: ARRIVE/ASPREE show smaller effect than observational. " +
      "Beta(2.5, 4.0) → mean 38%, 95% CI: 8-73%",
    calibrationSources: [
      "Danaei et al. 2012 (statin RCT vs observational)",
      "ARRIVE/ASPREE trials (aspirin less effective)",
    ],
  },

  // Social: Very skeptical - strong selection effects, no RCT possible
  social: {
    causalFraction: { alpha: 1.0, beta: 5.5 },
    rationale:
      "Social relationships heavily confounded with SES, mental health, physical health. " +
      "No RCT evidence possible for mortality endpoints. " +
      "Beta(1.0, 5.5) → mean 15%, 95% CI: 1-42%",
    calibrationSources: [
      "Holt-Lunstad et al. 2010 (observational only)",
    ],
  },

  // Other: Conservative prior when category unclear
  other: {
    causalFraction: { alpha: 1.2, beta: 4.8 },
    rationale:
      "Unknown intervention type; using conservative prior " +
      "reflecting general observational bias from calibration data. " +
      "Beta(1.2, 4.8) → mean 20%, 95% CI: 2-50%",
    calibrationSources: [],
  },
};

/**
 * Evidence type adjustments
 *
 * Applied as multipliers to the category-specific causal fraction.
 * RCT evidence needs less adjustment; observational needs more.
 */
export const EVIDENCE_ADJUSTMENTS: Record<
  "meta-analysis" | "rct" | "cohort" | "case-control" | "review" | "other",
  { multiplier: number; rationale: string }
> = {
  "meta-analysis": {
    multiplier: 1.1,
    rationale: "Meta-analyses aggregate evidence, slight upward adjustment",
  },
  rct: {
    multiplier: 1.5,
    rationale: "RCT evidence less confounded; higher causal fraction",
  },
  cohort: {
    multiplier: 0.8,
    rationale: "Cohort studies subject to healthy user bias",
  },
  "case-control": {
    multiplier: 0.7,
    rationale: "Case-control more prone to selection bias",
  },
  review: {
    multiplier: 1.0,
    rationale: "Narrative reviews; no adjustment",
  },
  other: {
    multiplier: 0.9,
    rationale: "Unknown study type; slight downward adjustment",
  },
};

/**
 * Get confounding configuration for an intervention
 */
export function getConfoundingConfig(
  category: string,
  primaryEvidenceType?: "meta-analysis" | "rct" | "cohort" | "case-control" | "review" | "other"
): ConfoundingConfig {
  const baseConfig =
    CONFOUNDING_BY_CATEGORY[category] || CONFOUNDING_BY_CATEGORY.other;

  if (!primaryEvidenceType) {
    return baseConfig;
  }

  // Adjust alpha based on evidence type (higher = more causal)
  const adjustment = EVIDENCE_ADJUSTMENTS[primaryEvidenceType];
  const adjustedAlpha = baseConfig.causalFraction.alpha * adjustment.multiplier;

  return {
    causalFraction: {
      alpha: adjustedAlpha,
      beta: baseConfig.causalFraction.beta,
    },
    rationale: `${baseConfig.rationale} Adjusted for ${primaryEvidenceType}: ${adjustment.rationale}`,
    calibrationSources: baseConfig.calibrationSources,
  };
}

/**
 * Sample a causal fraction from the Beta prior
 */
export function sampleCausalFraction(config: ConfoundingConfig): number {
  const { alpha, beta } = config.causalFraction;
  return sampleBeta(alpha, beta);
}

/**
 * Get expected (mean) causal fraction
 */
export function getExpectedCausalFraction(config: ConfoundingConfig): number {
  const { alpha, beta } = config.causalFraction;
  return alpha / (alpha + beta);
}

/**
 * Get credible interval for causal fraction
 */
export function getCausalFractionCI(
  config: ConfoundingConfig,
  level: number = 0.95
): { low: number; high: number } {
  const { alpha, beta } = config.causalFraction;
  const tailProb = (1 - level) / 2;

  return {
    low: betaQuantile(tailProb, alpha, beta),
    high: betaQuantile(1 - tailProb, alpha, beta),
  };
}

/**
 * Apply confounding adjustment to a hazard ratio
 *
 * For protective effects (HR < 1), we adjust toward 1:
 * log(HR_causal) = causalFraction × log(HR_observed)
 *
 * This shrinks the observed effect toward null by the confounding fraction.
 */
export function adjustHazardRatio(
  observedHR: number,
  causalFraction: number
): number {
  const logHR = Math.log(observedHR);
  const adjustedLogHR = causalFraction * logHR;
  return Math.exp(adjustedLogHR);
}

/**
 * Apply confounding adjustment to a distribution
 */
export function adjustDistribution(
  dist: Distribution,
  causalFraction: number
): Distribution {
  switch (dist.type) {
    case "point":
      return { type: "point", value: adjustHazardRatio(dist.value, causalFraction) };

    case "lognormal":
      // For lognormal (HRs), adjust the log-mean
      return {
        type: "lognormal",
        logMean: dist.logMean * causalFraction,
        logSd: dist.logSd * causalFraction, // Also shrink uncertainty
      };

    case "normal":
      // For normal, just scale the effect
      return {
        type: "normal",
        mean: dist.mean * causalFraction,
        sd: dist.sd * causalFraction,
      };

    default:
      return dist;
  }
}

/**
 * Calculate E-value for a relative risk
 *
 * The E-value quantifies the minimum strength of association an unmeasured
 * confounder would need with both exposure and outcome to fully explain
 * an observed association.
 *
 * For protective exposures (RR < 1), we first convert to RR > 1 by taking reciprocal.
 *
 * Formula: E = RR + sqrt(RR × (RR - 1))
 *
 * Reference: VanderWeele & Ding (2017)
 */
export function calculateEValue(observedHR: number): {
  eValue: number;
  interpretation: string;
} {
  // Convert to RR > 1 for protective effects
  const rr = observedHR < 1 ? 1 / observedHR : observedHR;

  // E-value formula
  const eValue = rr + Math.sqrt(rr * (rr - 1));

  // Interpretation
  let interpretation: string;
  if (eValue < 1.5) {
    interpretation =
      "Very susceptible to confounding. A weak confounder could explain this effect.";
  } else if (eValue < 2.0) {
    interpretation =
      "Moderately robust. A moderate confounder (RR ~2) could explain this effect.";
  } else if (eValue < 3.0) {
    interpretation =
      "Reasonably robust. Would require a strong confounder (RR ~2-3) to explain.";
  } else {
    interpretation =
      "Robust to confounding. Only a very strong confounder (RR >3) could fully explain.";
  }

  return { eValue, interpretation };
}

/**
 * Calculate E-value for the confidence interval bound
 * (How strong would a confounder need to be to shift CI to include null?)
 */
export function calculateEValueForCI(
  observedHR: number,
  ciLow: number,
  ciHigh: number
): {
  eValuePoint: number;
  eValueCI: number;
  interpretation: string;
} {
  const { eValue: eValuePoint } = calculateEValue(observedHR);

  // For the CI bound closest to null
  const ciBoundCloserToNull = observedHR < 1 ? ciHigh : ciLow;
  const { eValue: eValueCI } = calculateEValue(ciBoundCloserToNull);

  let interpretation: string;
  if (eValueCI < 1.1) {
    interpretation =
      "Confidence interval already includes null or nearly so. Effect uncertain.";
  } else if (eValueCI < 1.5) {
    interpretation =
      "CI bound has low E-value. Even weak confounding could explain away statistical significance.";
  } else {
    interpretation = `Point estimate E-value: ${eValuePoint.toFixed(2)}. CI bound E-value: ${eValueCI.toFixed(2)}.`;
  }

  return { eValuePoint, eValueCI, interpretation };
}

/**
 * Comprehensive confounding analysis result
 */
export interface ConfoundingAnalysis {
  category: string;
  evidenceType: string;
  config: ConfoundingConfig;

  /** Expected causal fraction (mean of Beta prior) */
  expectedCausalFraction: number;

  /** 95% credible interval for causal fraction */
  causalFractionCI: { low: number; high: number };

  /** E-value for robustness assessment */
  eValue: {
    point: number;
    interpretation: string;
  };

  /** Adjusted hazard ratio after applying causal fraction */
  adjustedHR: {
    original: number;
    adjusted: number;
    percentReduction: number;
  };
}

/**
 * Perform full confounding analysis for an intervention
 */
export function analyzeConfounding(
  category: string,
  observedHR: number,
  primaryEvidenceType?: "meta-analysis" | "rct" | "cohort" | "case-control" | "review" | "other"
): ConfoundingAnalysis {
  const config = getConfoundingConfig(category, primaryEvidenceType);
  const expectedCausalFraction = getExpectedCausalFraction(config);
  const causalFractionCI = getCausalFractionCI(config);
  const eValue = calculateEValue(observedHR);
  const adjustedHR = adjustHazardRatio(observedHR, expectedCausalFraction);

  // Calculate percent reduction in effect size
  const originalLogHR = Math.log(observedHR);
  const adjustedLogHR = Math.log(adjustedHR);
  const percentReduction =
    originalLogHR !== 0
      ? ((originalLogHR - adjustedLogHR) / originalLogHR) * 100
      : 0;

  return {
    category,
    evidenceType: primaryEvidenceType || "unknown",
    config,
    expectedCausalFraction,
    causalFractionCI,
    eValue: {
      point: eValue.eValue,
      interpretation: eValue.interpretation,
    },
    adjustedHR: {
      original: observedHR,
      adjusted: adjustedHR,
      percentReduction,
    },
  };
}

// ============================================
// Helper functions for Beta distribution
// ============================================

/**
 * Sample from Beta distribution using Gamma sampling
 */
function sampleBeta(alpha: number, beta: number): number {
  const gammaA = sampleGamma(alpha, 1);
  const gammaB = sampleGamma(beta, 1);
  return gammaA / (gammaA + gammaB);
}

/**
 * Sample from Gamma distribution (Marsaglia and Tsang's method)
 */
function sampleGamma(shape: number, scale: number): number {
  if (shape < 1) {
    return sampleGamma(1 + shape, scale) * Math.pow(random(), 1 / shape);
  }

  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);

  while (true) {
    let x: number;
    let v: number;

    do {
      const u1 = random();
      const u2 = random();
      x = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      v = 1 + c * x;
    } while (v <= 0);

    v = v * v * v;
    const u = random();

    if (u < 1 - 0.0331 * x * x * x * x) {
      return d * v * scale;
    }

    if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) {
      return d * v * scale;
    }
  }
}

/**
 * Beta quantile function (inverse CDF) using Newton-Raphson
 */
function betaQuantile(p: number, alpha: number, beta: number): number {
  // Use Newton-Raphson to find x such that I(x; α, β) = p
  // where I is the regularized incomplete beta function

  // Initial guess based on normal approximation
  let x = alpha / (alpha + beta);

  for (let i = 0; i < 50; i++) {
    const fx = incompleteBeta(x, alpha, beta) - p;
    const fpx = betaPdf(x, alpha, beta);

    if (Math.abs(fx) < 1e-10 || fpx === 0) break;

    x = x - fx / fpx;
    x = Math.max(1e-10, Math.min(1 - 1e-10, x)); // Keep in bounds
  }

  return x;
}

/**
 * Regularized incomplete beta function I(x; α, β)
 * Using continued fraction expansion
 */
function incompleteBeta(x: number, a: number, b: number): number {
  if (x === 0) return 0;
  if (x === 1) return 1;

  // Use symmetry relation if x > (a+1)/(a+b+2)
  if (x > (a + 1) / (a + b + 2)) {
    return 1 - incompleteBeta(1 - x, b, a);
  }

  // Continued fraction expansion
  const bt =
    Math.exp(
      logGamma(a + b) -
        logGamma(a) -
        logGamma(b) +
        a * Math.log(x) +
        b * Math.log(1 - x)
    );

  // Lentz's algorithm for continued fraction
  const eps = 1e-14;
  const maxIter = 200;

  let am = 1;
  let bm = 1;
  let az = 1;
  let bz = 1 - ((a + b) * x) / (a + 1);

  if (Math.abs(bz) < eps) bz = eps;

  let aold = 0;
  let em: number, tem: number, d: number, ap: number, bp: number, app: number, bpp: number;

  for (let m = 1; m <= maxIter; m++) {
    em = m;
    tem = em + em;

    // Even step
    d = (em * (b - em) * x) / ((a + tem - 1) * (a + tem));
    ap = az + d * am;
    bp = bz + d * bm;

    // Odd step
    d = (-(a + em) * (a + b + em) * x) / ((a + tem) * (a + tem + 1));
    app = ap + d * az;
    bpp = bp + d * bz;

    aold = az;
    am = ap / bpp;
    bm = bp / bpp;
    az = app / bpp;
    bz = 1;

    if (Math.abs(az - aold) < eps * Math.abs(az)) {
      return bt * az / a;
    }
  }

  return bt * az / a;
}

/**
 * Beta PDF
 */
function betaPdf(x: number, alpha: number, beta: number): number {
  if (x <= 0 || x >= 1) return 0;
  return (
    Math.exp(
      (alpha - 1) * Math.log(x) +
        (beta - 1) * Math.log(1 - x) +
        logGamma(alpha + beta) -
        logGamma(alpha) -
        logGamma(beta)
    )
  );
}

/**
 * Log-Gamma function using Lanczos approximation
 */
function logGamma(z: number): number {
  if (z < 0.5) {
    return Math.log(Math.PI / Math.sin(Math.PI * z)) - logGamma(1 - z);
  }

  z -= 1;

  const g = 7;
  const c = [
    0.99999999999980993, 676.5203681218851, -1259.1392167224028,
    771.32342877765313, -176.61502916214059, 12.507343278686905,
    -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7,
  ];

  let x = c[0];
  for (let i = 1; i < g + 2; i++) {
    x += c[i] / (z + i);
  }

  const t = z + g + 0.5;
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}
