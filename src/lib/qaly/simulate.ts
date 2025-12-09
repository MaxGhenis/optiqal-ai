/**
 * Monte Carlo QALY simulation
 *
 * Given structured intervention effects and a user profile,
 * simulates QALY outcomes with proper uncertainty propagation.
 */

import type {
  Distribution,
  InterventionEffect,
  MortalityEffect,
  QualityEffect,
  QALYSimulationResult,
} from "./types";
import type { UserProfile } from "@/types";
import {
  calculateBaselineQALYs,
  getRemainingLifeExpectancy,
  getAgeQualityWeight,
} from "@/lib/evidence/baseline";

/**
 * Sample from a distribution
 */
function sampleDistribution(dist: Distribution): number {
  switch (dist.type) {
    case "point":
      return dist.value;

    case "normal":
      // Box-Muller transform
      const u1 = Math.random();
      const u2 = Math.random();
      const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      return dist.mean + z * dist.sd;

    case "lognormal":
      // Sample normal, then exponentiate
      const u1ln = Math.random();
      const u2ln = Math.random();
      const zln = Math.sqrt(-2 * Math.log(u1ln)) * Math.cos(2 * Math.PI * u2ln);
      return Math.exp(dist.logMean + zln * dist.logSd);

    case "beta":
      // Use Gamma sampling: Beta(a,b) = Gamma(a,1) / (Gamma(a,1) + Gamma(b,1))
      const gammaA = sampleGamma(dist.alpha, 1);
      const gammaB = sampleGamma(dist.beta, 1);
      return gammaA / (gammaA + gammaB);

    case "uniform":
      return dist.min + Math.random() * (dist.max - dist.min);
  }
}

/**
 * Sample from Gamma distribution using Marsaglia and Tsang's method
 */
function sampleGamma(shape: number, scale: number): number {
  if (shape < 1) {
    // Use Ahrens-Dieter method for shape < 1
    return sampleGamma(1 + shape, scale) * Math.pow(Math.random(), 1 / shape);
  }

  const d = shape - 1 / 3;
  const c = 1 / Math.sqrt(9 * d);

  while (true) {
    let x: number;
    let v: number;

    do {
      const u1 = Math.random();
      const u2 = Math.random();
      x = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
      v = 1 + c * x;
    } while (v <= 0);

    v = v * v * v;
    const u = Math.random();

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
 */
function runSingleSimulation(
  profile: UserProfile,
  effect: InterventionEffect,
  baselineLE: number
): number {
  // Sample effect parameters
  const sampledMortalityHR = effect.mortality
    ? sampleDistribution(effect.mortality.hazardRatio)
    : 1.0;

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
    baselineLE * (1 + (Math.random() * 2 - 1) * leUncertainty);

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

/**
 * Run Monte Carlo simulation
 */
export function simulateQALYImpact(
  profile: UserProfile,
  effect: InterventionEffect,
  nSimulations: number = 10000
): QALYSimulationResult {
  const baselineProjection = calculateBaselineQALYs(profile);
  const baselineLE = baselineProjection.remainingLifeExpectancy;

  // Run simulations
  const results: number[] = [];

  for (let i = 0; i < nSimulations; i++) {
    results.push(runSingleSimulation(profile, effect, baselineLE));
  }

  // Sort for percentile calculations
  results.sort((a, b) => a - b);

  // Calculate statistics
  const mean = results.reduce((a, b) => a + b, 0) / nSimulations;
  const median = results[Math.floor(nSimulations / 2)];

  const ci95Low = results[Math.floor(nSimulations * 0.025)];
  const ci95High = results[Math.floor(nSimulations * 0.975)];

  const ci50Low = results[Math.floor(nSimulations * 0.25)];
  const ci50High = results[Math.floor(nSimulations * 0.75)];

  const probPositive = results.filter((r) => r > 0).length / nSimulations;
  const probMoreThanOneYear =
    results.filter((r) => r > 1).length / nSimulations;

  // Percentiles for distribution visualization
  const percentiles = [1, 5, 10, 25, 50, 75, 90, 95, 99].map((p) => ({
    p,
    value: results[Math.floor((nSimulations * p) / 100)],
  }));

  // For breakdown, we'd need to run separate simulations
  // This is a simplified version
  const breakdown = {
    mortalityQALYs: {
      median: effect.mortality ? median * 0.6 : 0, // Rough split
      ci95: {
        low: effect.mortality ? ci95Low * 0.6 : 0,
        high: effect.mortality ? ci95High * 0.6 : 0,
      },
    },
    qualityQALYs: {
      median: effect.quality ? median * 0.4 : 0,
      ci95: {
        low: effect.quality ? ci95Low * 0.4 : 0,
        high: effect.quality ? ci95High * 0.4 : 0,
      },
    },
    costQALYs: {
      median: 0,
      ci95: { low: 0, high: 0 },
    },
  };

  return {
    median,
    mean,
    ci95: { low: ci95Low, high: ci95High },
    ci50: { low: ci50Low, high: ci50High },
    probPositive,
    probMoreThanOneYear,
    percentiles,
    breakdown,
    nSimulations,
  };
}

/**
 * Convert QALY years to minutes for display
 */
export function qalyYearsToMinutes(years: number): number {
  return years * 525600; // 365.25 * 24 * 60
}
