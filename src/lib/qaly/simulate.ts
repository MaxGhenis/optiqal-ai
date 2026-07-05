/**
 * Monte Carlo QALY simulation
 *
 * Given structured intervention effects and a user profile,
 * simulates QALY outcomes with proper uncertainty propagation.
 *
 * Includes confounding adjustment based on whatnut methodology:
 * - Category-specific Beta priors for causal fraction
 * - Evidence type adjustments (RCT vs cohort)
 * - E-value calculation for robustness assessment
 */

import type {
  Distribution,
  InterventionEffect,
  MortalityEffect,
  QualityEffect,
  QALYSimulationResult,
  SimulationOptions,
  ConfoundingResult,
} from "./types";
import type { UserProfile } from "@/types";
import {
  calculateBaselineQALYs,
  getAgeQualityWeight,
} from "@/lib/evidence/baseline";
import {
  getConfoundingConfig,
  sampleCausalFraction,
  getExpectedCausalFraction,
  getCausalFractionCI,
  adjustHazardRatio,
  calculateEValue,
  type ConfoundingConfig,
} from "./confounding";
import { random, setSeed } from "./random";

/**
 * Uncertainty multipliers based on evidence quality
 *
 * Weaker evidence → wider confidence intervals (inflated SD)
 * This keeps the point estimate the same but increases uncertainty.
 *
 * Based on GRADE methodology and Cochrane guidelines:
 * - High quality: 1x (no inflation)
 * - Moderate: 1.5x
 * - Low: 2x
 * - Very low: 3x
 */
export const EVIDENCE_UNCERTAINTY_MULTIPLIERS: Record<string, number> = {
  high: 1.0,
  strong: 1.0,
  moderate: 1.5,
  low: 2.0,
  weak: 2.0,
  "very-low": 3.0,
};

/**
 * Sample from a distribution with optional uncertainty inflation
 *
 * @param dist - The distribution to sample from
 * @param uncertaintyMultiplier - Multiplier for SD (1.0 = no inflation)
 */
function sampleDistribution(dist: Distribution, uncertaintyMultiplier: number = 1.0): number {
  switch (dist.type) {
    case "point":
      // Point estimates can't be inflated; return as-is
      return dist.value;

    case "normal":
      // Box-Muller transform with inflated SD
      const u1 = random();
      const u2 = random();
      const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      return dist.mean + z * (dist.sd * uncertaintyMultiplier);

    case "lognormal":
      // Sample normal in log space, then exponentiate, inflating logSd by the
      // evidence-quality multiplier. This preserves the median (exp(logMean)) —
      // the point estimate shown to users — while widening the interval. The
      // mean (exp(logMean + logSd²/2)) does rise with logSd; that reflects the
      // skew of integrating over genuine epistemic uncertainty and is intended,
      // not a drift in the central estimate.
      const u1ln = random();
      const u2ln = random();
      const zln = Math.sqrt(-2 * Math.log(u1ln)) * Math.cos(2 * Math.PI * u2ln);
      return Math.exp(dist.logMean + zln * (dist.logSd * uncertaintyMultiplier));

    case "beta":
      // For Beta, reduce concentration to widen while keeping mean
      // mean = α/(α+β), so we scale both by 1/multiplier² to widen
      const scale = 1 / (uncertaintyMultiplier * uncertaintyMultiplier);
      const scaledAlpha = Math.max(0.5, dist.alpha * scale);
      const scaledBeta = Math.max(0.5, dist.beta * scale);
      const gammaA = sampleGamma(scaledAlpha, 1);
      const gammaB = sampleGamma(scaledBeta, 1);
      return gammaA / (gammaA + gammaB);

    case "uniform":
      // Widen the range symmetrically around the midpoint
      const mid = (dist.min + dist.max) / 2;
      const halfRange = (dist.max - dist.min) / 2;
      const inflatedHalfRange = halfRange * uncertaintyMultiplier;
      return mid + (random() * 2 - 1) * inflatedHalfRange;
  }
}

/**
 * Sample from Gamma distribution using Marsaglia and Tsang's method
 */
function sampleGamma(shape: number, scale: number): number {
  if (shape < 1) {
    // Use Ahrens-Dieter method for shape < 1
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
 * Calculate mortality effect at a given year, accounting for onset/decay
 */
function getMortalityEffectAtYear(
  effect: MortalityEffect,
  year: number,
  sampledHR: number
): number {
  // Before onset, no effect
  if (year < effect.onsetDelay) {
    return 1.0; // HR = 1 means no change
  }

  // During ramp-up period
  const yearsSinceOnset = year - effect.onsetDelay;
  let effectStrength = 1.0;

  if (effect.rampUpPeriod > 0 && yearsSinceOnset < effect.rampUpPeriod) {
    effectStrength = yearsSinceOnset / effect.rampUpPeriod;
  }

  // Apply decay
  if (effect.decayRate > 0) {
    const decayYears = Math.max(0, yearsSinceOnset - effect.rampUpPeriod);
    effectStrength *= Math.exp(-effect.decayRate * decayYears);
  }

  // Interpolate between HR=1 (no effect) and sampled HR
  // effectStrength of 1.0 means full sampled HR
  // effectStrength of 0.0 means HR = 1
  return 1.0 + effectStrength * (sampledHR - 1.0);
}

/**
 * Calculate quality effect at a given year
 */
function getQualityEffectAtYear(
  effect: QualityEffect,
  year: number,
  sampledUtilityChange: number
): number {
  if (year < effect.onsetDelay) {
    return 0;
  }

  const yearsSinceOnset = year - effect.onsetDelay;
  let effectStrength = 1.0;

  // Apply decay
  if (effect.decayRate > 0) {
    effectStrength = Math.exp(-effect.decayRate * yearsSinceOnset);
  }

  return sampledUtilityChange * effectStrength;
}

/**
 * Run single simulation to get QALY impact
 *
 * @param causalFraction - If provided, applies confounding adjustment to mortality HR
 */
function runSingleSimulation(
  profile: UserProfile,
  effect: InterventionEffect,
  baselineLE: number,
  causalFraction?: number
): number {
  // Sample effect parameters
  let sampledMortalityHR = effect.mortality
    ? sampleDistribution(effect.mortality.hazardRatio)
    : 1.0;

  // Apply confounding adjustment if causal fraction provided
  if (causalFraction !== undefined && sampledMortalityHR !== 1.0) {
    sampledMortalityHR = adjustHazardRatio(sampledMortalityHR, causalFraction);
  }

  // For quality, we sum up subjective wellbeing and direct dimension effects
  let sampledQualityChange = 0;
  if (effect.quality) {
    // Subjective wellbeing effect
    if (effect.quality.subjectiveWellbeing) {
      sampledQualityChange += sampleDistribution(effect.quality.subjectiveWellbeing);
    }
    // Direct dimension effects (simplified: just average them)
    for (const dimEffect of effect.quality.directDimensionEffects) {
      sampledQualityChange += sampleDistribution(dimEffect.change) / 5; // 5 dimensions
    }
  }

  // Add some uncertainty to baseline life expectancy (~10% CV)
  const leUncertainty = 0.1;
  const sampledLE =
    baselineLE * (1 + (random() * 2 - 1) * leUncertainty);

  // Simulate year by year
  let baselineQALYs = 0;
  let interventionQALYs = 0;

  for (let year = 0; year < Math.ceil(sampledLE); year++) {
    const currentAge = profile.age + year;
    const fractionOfYear = Math.min(1, sampledLE - year);

    // Baseline quality weight
    const baseQuality = getAgeQualityWeight(currentAge);

    // Baseline survival (simplified - just linear decay to 0)
    const baselineSurvival = Math.max(0, 1 - year / sampledLE);

    // Baseline QALY contribution for this year
    baselineQALYs += baseQuality * baselineSurvival * fractionOfYear;

    // Intervention effects
    const yearMortalityHR = effect.mortality
      ? getMortalityEffectAtYear(effect.mortality, year, sampledMortalityHR)
      : 1.0;

    const yearQualityChange = effect.quality
      ? getQualityEffectAtYear(effect.quality, year, sampledQualityChange)
      : 0;

    // Modified survival: lower HR = better survival
    // This is simplified; proper implementation would use hazard functions
    const survivalModifier = Math.pow(yearMortalityHR, -0.1); // Rough approximation
    const interventionSurvival = Math.min(
      1,
      baselineSurvival * survivalModifier
    );

    // Modified quality
    const interventionQuality = Math.min(
      1,
      Math.max(0, baseQuality + yearQualityChange)
    );

    // Intervention QALY contribution
    interventionQALYs +=
      interventionQuality * interventionSurvival * fractionOfYear;
  }

  // Return the difference (QALY gain from intervention)
  return interventionQALYs - baselineQALYs;
}

function getPercentileValue(sortedValues: number[], percentile: number): number {
  const index = Math.min(
    sortedValues.length - 1,
    Math.floor((sortedValues.length * percentile) / 100)
  );
  return sortedValues[index];
}

/**
 * Summarize the unadjusted (causalFraction = 1) draws against the adjusted
 * posterior median. Uses the real simulated unadjusted median rather than
 * rescaling the adjusted median by the causal fraction, which would be wrong
 * because QALY gain is nonlinear in the causal fraction.
 */
function buildConfoundingComparison(
  unadjustedResults: number[],
  adjustedMedian: number
): { unadjustedMedian: number; adjustedMedian: number; reductionPercent: number } {
  if (unadjustedResults.length === 0) {
    return { unadjustedMedian: adjustedMedian, adjustedMedian, reductionPercent: 0 };
  }
  const sorted = [...unadjustedResults].sort((a, b) => a - b);
  const unadjustedMedian = sorted[Math.floor(sorted.length / 2)];
  const reductionPercent =
    unadjustedMedian !== 0
      ? (1 - adjustedMedian / unadjustedMedian) * 100
      : 0;
  return { unadjustedMedian, adjustedMedian, reductionPercent };
}

function summarizePosterior(sortedResults: number[]) {
  const n = sortedResults.length;

  let sum = 0;
  let positiveCount = 0;
  let negativeCount = 0;
  let greaterThanOneYearCount = 0;
  let upsideSum = 0;
  let downsideSum = 0;

  for (const value of sortedResults) {
    sum += value;
    if (value > 0) {
      positiveCount += 1;
      upsideSum += value;
    } else if (value < 0) {
      negativeCount += 1;
      downsideSum += value;
    }
    if (value > 1) {
      greaterThanOneYearCount += 1;
    }
  }

  return {
    mean: sum / n,
    median: getPercentileValue(sortedResults, 50),
    ci95: {
      low: getPercentileValue(sortedResults, 2.5),
      high: getPercentileValue(sortedResults, 97.5),
    },
    ci50: {
      low: getPercentileValue(sortedResults, 25),
      high: getPercentileValue(sortedResults, 75),
    },
    probPositive: positiveCount / n,
    probNegative: negativeCount / n,
    probMoreThanOneYear: greaterThanOneYearCount / n,
    expectedUpside: upsideSum / n,
    expectedDownside: downsideSum / n,
    conditionalUpside: positiveCount > 0 ? upsideSum / positiveCount : 0,
    conditionalDownside: negativeCount > 0 ? downsideSum / negativeCount : 0,
    percentiles: [1, 5, 10, 25, 50, 75, 90, 95, 99].map((p) => ({
      p,
      value: getPercentileValue(sortedResults, p),
    })),
  };
}

/**
 * Run Monte Carlo simulation with optional confounding adjustment
 *
 * By default, applies category-specific confounding adjustment based on
 * intervention type and evidence quality. This adjusts mortality hazard
 * ratios to account for healthy user bias in observational studies.
 */
export function simulateQALYImpact(
  profile: UserProfile,
  effect: InterventionEffect,
  options: SimulationOptions = {}
): QALYSimulationResult {
  const {
    nSimulations = 10000,
    applyConfounding = true,
    confoundingOverride,
    evidenceType,
    seed = 42,
  } = options;

  // Set seed for reproducibility
  setSeed(seed);

  const baselineProjection = calculateBaselineQALYs(profile);
  const baselineLE = baselineProjection.remainingLifeExpectancy;

  // Set up confounding config
  let confoundingConfig: ConfoundingConfig | null = null;
  if (applyConfounding) {
    if (confoundingOverride) {
      confoundingConfig = {
        causalFraction: confoundingOverride,
        rationale: "User-provided override",
        calibrationSources: [],
      };
    } else {
      confoundingConfig = getConfoundingConfig(effect.category, evidenceType);
    }
  }

  // Run adjusted simulations
  const results: number[] = [];
  for (let i = 0; i < nSimulations; i++) {
    // Sample causal fraction for each simulation (propagates uncertainty)
    const causalFraction = confoundingConfig
      ? sampleCausalFraction(confoundingConfig)
      : undefined;
    results.push(runSingleSimulation(profile, effect, baselineLE, causalFraction));
  }

  // Also run unadjusted simulations for comparison (smaller sample for speed)
  const unadjustedResults: number[] = [];
  if (confoundingConfig) {
    const unadjustedN = Math.min(1000, nSimulations);
    for (let i = 0; i < unadjustedN; i++) {
      unadjustedResults.push(runSingleSimulation(profile, effect, baselineLE));
    }
    unadjustedResults.sort((a, b) => a - b);
  }

  // Sort for percentile calculations
  results.sort((a, b) => a - b);
  const posterior = summarizePosterior(results);

  // For breakdown, we'd need to run separate simulations
  // This is a simplified version
  const breakdown = {
    mortalityQALYs: {
      median: effect.mortality ? posterior.median * 0.6 : 0, // Rough split
      ci95: {
        low: effect.mortality ? posterior.ci95.low * 0.6 : 0,
        high: effect.mortality ? posterior.ci95.high * 0.6 : 0,
      },
    },
    qualityQALYs: {
      median: effect.quality ? posterior.median * 0.4 : 0,
      ci95: {
        low: effect.quality ? posterior.ci95.low * 0.4 : 0,
        high: effect.quality ? posterior.ci95.high * 0.4 : 0,
      },
    },
    costQALYs: {
      median: 0,
      ci95: { low: 0, high: 0 },
    },
  };

  // Build confounding result if applicable
  let confounding: ConfoundingResult | undefined;
  if (confoundingConfig && effect.mortality) {
    // Get the expected (median) HR from the mortality distribution
    const expectedHR = getDistributionMean(effect.mortality.hazardRatio);
    const { eValue, interpretation } = calculateEValue(expectedHR);

    // Calculate E-value for CI bound (approximate from lognormal)
    const hrSD = getDistributionSD(effect.mortality.hazardRatio);
    const ciHighHR = expectedHR * Math.exp(1.96 * Math.log(1 + hrSD / expectedHR));
    const { eValue: eValueCI } = calculateEValue(ciHighHR);

    const unadjustedMedian = unadjustedResults.length > 0
      ? summarizePosterior(unadjustedResults).median
      : posterior.median;

    const reductionPercent = unadjustedMedian !== 0
      ? ((unadjustedMedian - posterior.median) / unadjustedMedian) * 100
      : 0;

    confounding = {
      applied: true,
      expectedCausalFraction: getExpectedCausalFraction(confoundingConfig),
      causalFractionCI: getCausalFractionCI(confoundingConfig),
      eValue: {
        point: eValue,
        ciLow: eValueCI,
        interpretation,
      },
      comparison: {
        unadjustedMedian,
        adjustedMedian: posterior.median,
        reductionPercent,
      },
    };
  }

  return {
    median: posterior.median,
    mean: posterior.mean,
    ci95: posterior.ci95,
    ci50: posterior.ci50,
    probPositive: posterior.probPositive,
    probNegative: posterior.probNegative,
    probMoreThanOneYear: posterior.probMoreThanOneYear,
    expectedUpside: posterior.expectedUpside,
    expectedDownside: posterior.expectedDownside,
    conditionalUpside: posterior.conditionalUpside,
    conditionalDownside: posterior.conditionalDownside,
    percentiles: posterior.percentiles,
    breakdown,
    confounding,
    nSimulations,
  };
}

/**
 * Get mean/expected value of a distribution (local helper)
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
 * Get standard deviation of a distribution (local helper)
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
 * Convert QALY years to minutes for display
 */
export function qalyYearsToMinutes(years: number): number {
  return years * 525600; // 365.25 * 24 * 60
}

// ============================================
// RIGOROUS LIFECYCLE SIMULATION
// ============================================

import {
  calculateLifecycleQALYs,
  type PathwayHRs,
} from "./lifecycle";

/**
 * Extended simulation result with lifecycle details
 */
export interface RigorousSimulationResult extends QALYSimulationResult {
  /** Lifecycle model details */
  lifecycle: {
    /** Pathway-specific QALY contributions */
    pathwayContributions: {
      cvd: { median: number; ci95: { low: number; high: number } };
      cancer: { median: number; ci95: { low: number; high: number } };
      other: { median: number; ci95: { low: number; high: number } };
    };

    /** Life years gained (undiscounted) */
    lifeYearsGained: { median: number; ci95: { low: number; high: number } };

    /** Discount rate used */
    discountRate: number;

    /** Whether lifecycle model was used */
    used: boolean;
  };
}

/**
 * Options for rigorous simulation
 */
export interface RigorousSimulationOptions extends SimulationOptions {
  /** Use rigorous lifecycle model (default: true) */
  useLifecycleModel?: boolean;

  /** Discount rate (default: 0.03 = 3%) */
  discountRate?: number;

  /** Pathway-specific HRs (if not provided, derived from overall HR) */
  pathwayHRs?: PathwayHRs;

  /** Evidence quality - affects CI width, NOT point estimate */
  evidenceQuality?: "high" | "moderate" | "low" | "very-low" | "strong" | "weak";
}

/**
 * Run rigorous Monte Carlo simulation with lifecycle model
 *
 * This version uses:
 * - CDC life tables for survival curves
 * - Pathway decomposition (CVD, cancer, other)
 * - Age-varying cause fractions
 * - Proper discounting
 * - Confounding adjustment
 */
export function simulateQALYImpactRigorous(
  profile: UserProfile,
  effect: InterventionEffect,
  options: RigorousSimulationOptions = {}
): RigorousSimulationResult {
  const {
    nSimulations = 10000,
    applyConfounding = true,
    confoundingOverride,
    evidenceType,
    useLifecycleModel = true,
    discountRate = 0.03,
    pathwayHRs: customPathwayHRs,
    evidenceQuality,
    seed = 42,
  } = options;

  // Set seed for reproducibility
  setSeed(seed);

  // Get uncertainty multiplier based on evidence quality
  // Weaker evidence → wider CIs (same point estimate)
  const uncertaintyMultiplier = evidenceQuality
    ? EVIDENCE_UNCERTAINTY_MULTIPLIERS[evidenceQuality] || 1.0
    : effect.evidenceQuality
      ? EVIDENCE_UNCERTAINTY_MULTIPLIERS[effect.evidenceQuality] || 1.0
      : 1.0;

  // If not using lifecycle model, fall back to basic simulation
  if (!useLifecycleModel) {
    const basicResult = simulateQALYImpact(profile, effect, options);
    return {
      ...basicResult,
      lifecycle: {
        pathwayContributions: {
          cvd: { median: 0, ci95: { low: 0, high: 0 } },
          cancer: { median: 0, ci95: { low: 0, high: 0 } },
          other: { median: 0, ci95: { low: 0, high: 0 } },
        },
        lifeYearsGained: { median: 0, ci95: { low: 0, high: 0 } },
        discountRate,
        used: false,
      },
    };
  }

  // Set up confounding config
  let confoundingConfig: ConfoundingConfig | null = null;
  if (applyConfounding) {
    if (confoundingOverride) {
      confoundingConfig = {
        causalFraction: confoundingOverride,
        rationale: "User-provided override",
        calibrationSources: [],
      };
    } else {
      confoundingConfig = getConfoundingConfig(effect.category, evidenceType);
    }
  }

  // Get base mortality HR from effect
  const baseHR = effect.mortality
    ? getDistributionMean(effect.mortality.hazardRatio)
    : 1.0;

  // Derive pathway HRs from overall HR if not provided
  // Using standard pathway weights from Aune et al.
  const basePathwayHRs: PathwayHRs = customPathwayHRs || {
    cvd: Math.exp(Math.log(baseHR) * 1.3), // CVD gets stronger effect
    cancer: Math.exp(Math.log(baseHR) * 0.8),
    other: Math.exp(Math.log(baseHR) * 0.6),
  };

  // Run Monte Carlo simulations
  const results: number[] = [];
  const cvdContributions: number[] = [];
  const cancerContributions: number[] = [];
  const otherContributions: number[] = [];
  const lifeYearsResults: number[] = [];
  const qualityResults: number[] = [];
  // Paired draws with no confounding adjustment (causalFraction = 1), used to
  // report a *real* unadjusted-vs-adjusted comparison instead of dividing the
  // adjusted median by the causal fraction (QALY gain is nonlinear in it).
  const unadjustedResults: number[] = [];

  const sex = profile.sex === "female" ? "female" : "male";

  // Get baseline life expectancy for quality calculations
  const baselineProjection = calculateBaselineQALYs(profile);
  const baselineLE = baselineProjection.remainingLifeExpectancy;

  // Accumulate discounted quality QALYs for an (already confounding-scaled)
  // annual quality change, respecting any onset delay.
  const accumulateQualityQALY = (qualityChange: number): number => {
    if (!effect.quality) return 0;
    let q = 0;
    for (let year = 0; year < Math.ceil(baselineLE); year++) {
      const fractionOfYear = Math.min(1, baselineLE - year);
      const discountFactor = Math.pow(1 + discountRate, -year);
      const effectiveQuality =
        effect.quality.onsetDelay > 0 && year < effect.quality.onsetDelay
          ? 0
          : qualityChange;
      q += effectiveQuality * fractionOfYear * discountFactor;
    }
    return q;
  };

  for (let i = 0; i < nSimulations; i++) {
    // Sample causal fraction
    const causalFraction = confoundingConfig
      ? sampleCausalFraction(confoundingConfig)
      : 1.0;

    // Sample HR uncertainty (inflated by evidence quality)
    const hrMultiplier = effect.mortality
      ? sampleDistribution(effect.mortality.hazardRatio, uncertaintyMultiplier) / baseHR
      : 1.0;

    // Adjust pathway HRs by causal fraction and sampled uncertainty
    const adjustedPathwayHRs: PathwayHRs = {
      cvd: adjustHazardRatio(basePathwayHRs.cvd * hrMultiplier, causalFraction),
      cancer: adjustHazardRatio(basePathwayHRs.cancer * hrMultiplier, causalFraction),
      other: adjustHazardRatio(basePathwayHRs.other * hrMultiplier, causalFraction),
    };

    // Run lifecycle calculation for mortality
    const lifecycleResult = calculateLifecycleQALYs({
      startAge: profile.age,
      sex,
      pathwayHRs: adjustedPathwayHRs,
      discountRate,
    });

    // Sample the raw (pre-confounding) annual quality change once, then scale
    // by the causal fraction for the adjusted track.
    let rawQualityChange = 0;
    if (effect.quality) {
      if (effect.quality.subjectiveWellbeing) {
        rawQualityChange += sampleDistribution(effect.quality.subjectiveWellbeing, uncertaintyMultiplier);
      }
      for (const dimEffect of effect.quality.directDimensionEffects) {
        rawQualityChange += sampleDistribution(dimEffect.change, uncertaintyMultiplier) / 5;
      }
    }
    const qualityQALY = accumulateQualityQALY(rawQualityChange * causalFraction);

    results.push(lifecycleResult.qalyGain + qualityQALY);
    cvdContributions.push(lifecycleResult.pathwayContributions.cvd);
    cancerContributions.push(lifecycleResult.pathwayContributions.cancer);
    otherContributions.push(lifecycleResult.pathwayContributions.other);
    lifeYearsResults.push(lifecycleResult.lifeYearsGained);
    qualityResults.push(qualityQALY);

    // Paired unadjusted draw (causalFraction = 1) reusing the same sampled
    // HR multiplier and quality change, so the confounding comparison is a real
    // simulated difference rather than an algebraic rescaling. Gated on
    // effect.mortality to match where unadjustedResults is consumed below —
    // otherwise a quality-only intervention would compute these draws and
    // discard them. (These draws consume no RNG, so gating them does not change
    // the adjusted results.)
    if (confoundingConfig && effect.mortality) {
      const unadjustedPathwayHRs: PathwayHRs = {
        cvd: adjustHazardRatio(basePathwayHRs.cvd * hrMultiplier, 1.0),
        cancer: adjustHazardRatio(basePathwayHRs.cancer * hrMultiplier, 1.0),
        other: adjustHazardRatio(basePathwayHRs.other * hrMultiplier, 1.0),
      };
      const unadjustedLifecycle = calculateLifecycleQALYs({
        startAge: profile.age,
        sex,
        pathwayHRs: unadjustedPathwayHRs,
        discountRate,
      });
      unadjustedResults.push(
        unadjustedLifecycle.qalyGain + accumulateQualityQALY(rawQualityChange)
      );
    }
  }

  // Sort for percentile calculations
  results.sort((a, b) => a - b);
  cvdContributions.sort((a, b) => a - b);
  cancerContributions.sort((a, b) => a - b);
  otherContributions.sort((a, b) => a - b);
  lifeYearsResults.sort((a, b) => a - b);
  qualityResults.sort((a, b) => a - b);
  const posterior = summarizePosterior(results);

  // Build confounding result
  let confounding: ConfoundingResult | undefined;
  if (confoundingConfig && effect.mortality) {
    const expectedHR = getDistributionMean(effect.mortality.hazardRatio);
    const { eValue, interpretation } = calculateEValue(expectedHR);
    const hrSD = getDistributionSD(effect.mortality.hazardRatio);
    const ciHighHR = expectedHR * Math.exp(1.96 * Math.log(1 + hrSD / expectedHR));
    const { eValue: eValueCI } = calculateEValue(ciHighHR);

    confounding = {
      applied: true,
      expectedCausalFraction: getExpectedCausalFraction(confoundingConfig),
      causalFractionCI: getCausalFractionCI(confoundingConfig),
      eValue: {
        point: eValue,
        ciLow: eValueCI,
        interpretation,
      },
      comparison: buildConfoundingComparison(unadjustedResults, posterior.median),
    };
  }

  // Helper to get CI from sorted array
  const getCI = (arr: number[]) => ({
    median: arr[Math.floor(arr.length / 2)],
    ci95: {
      low: arr[Math.floor(arr.length * 0.025)],
      high: arr[Math.floor(arr.length * 0.975)],
    },
  });

  return {
    median: posterior.median,
    mean: posterior.mean,
    ci95: posterior.ci95,
    ci50: posterior.ci50,
    probPositive: posterior.probPositive,
    probNegative: posterior.probNegative,
    probMoreThanOneYear: posterior.probMoreThanOneYear,
    expectedUpside: posterior.expectedUpside,
    expectedDownside: posterior.expectedDownside,
    conditionalUpside: posterior.conditionalUpside,
    conditionalDownside: posterior.conditionalDownside,
    percentiles: posterior.percentiles,
    breakdown: {
      mortalityQALYs: {
        median: posterior.median - getCI(qualityResults).median, // Subtract quality to get pure mortality
        ci95: posterior.ci95,
      },
      qualityQALYs: getCI(qualityResults),
      costQALYs: {
        median: 0,
        ci95: { low: 0, high: 0 },
      },
    },
    confounding,
    nSimulations,
    lifecycle: {
      pathwayContributions: {
        cvd: getCI(cvdContributions),
        cancer: getCI(cancerContributions),
        other: getCI(otherContributions),
      },
      lifeYearsGained: getCI(lifeYearsResults),
      discountRate,
      used: true,
    },
  };
}
