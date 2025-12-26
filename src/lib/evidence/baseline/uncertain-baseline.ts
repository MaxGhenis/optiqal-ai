/**
 * Uncertain Baseline Calculation
 *
 * Calculates QALY predictions with proper uncertainty quantification.
 * When profile fields are unknown, we sample from population distributions,
 * resulting in wider prediction intervals.
 *
 * Key insight: As users provide more information, the prediction interval
 * shrinks because we're conditioning on more data rather than marginalizing.
 */

import {
  type PartialProfile,
  sampleCompleteProfile,
  calculateProfileCompleteness,
  partialToMeanProfile,
} from "./partial-profile";
import { calculateBaselineQALYs, type BaselineProjection } from "./index";
import { random, setSeed } from "@/lib/qaly/random";

/**
 * Result of uncertain baseline calculation
 */
export interface UncertainBaselineResult {
  // Point estimates (using population means for unknowns)
  pointEstimate: {
    remainingQALYs: number;
    remainingLifeExpectancy: number;
    expectedDeathAge: number;
    currentQualityWeight: number;
  };

  // Prediction intervals from Monte Carlo
  predictionInterval: {
    remainingQALYs: {
      p5: number;   // 5th percentile
      p25: number;  // 25th percentile
      p50: number;  // median
      p75: number;  // 75th percentile
      p95: number;  // 95th percentile
    };
    remainingLifeExpectancy: {
      p5: number;
      p25: number;
      p50: number;
      p75: number;
      p95: number;
    };
  };

  // How complete is the profile (0-1)
  completeness: number;

  // Interval width (for visualization)
  intervalWidth: {
    qalys: number;  // p95 - p5
    lifeYears: number;
  };

  // Simulation metadata
  nSimulations: number;

  // Full distribution for visualization
  distribution: {
    qalys: number[];
    lifeYears: number[];
  };

  // Survival curve with uncertainty bands
  survivalCurve: {
    age: number;
    survivalP50: number;
    survivalP5: number;
    survivalP95: number;
    qalyP50: number;
    qalyP5: number;
    qalyP95: number;
  }[];
}

/**
 * Calculate baseline QALYs with uncertainty for a partial profile
 *
 * @param partial - Partial profile (only age required)
 * @param options - Simulation options
 */
export function calculateBaselineWithUncertainty(
  partial: PartialProfile,
  options: {
    nSimulations?: number;
    seed?: number;
  } = {}
): UncertainBaselineResult {
  const { nSimulations = 1000, seed = 42 } = options;

  setSeed(seed);

  // Calculate completeness
  const completeness = calculateProfileCompleteness(partial);

  // Get point estimate using population means
  const meanProfile = partialToMeanProfile(partial);
  const pointProjection = calculateBaselineQALYs(meanProfile);

  // Run Monte Carlo simulations
  const qalyResults: number[] = [];
  const leResults: number[] = [];

  // For survival curve uncertainty, we need to track by age
  const survivalByAge: Map<number, { survival: number[]; qaly: number[] }> = new Map();

  for (let i = 0; i < nSimulations; i++) {
    // Sample a complete profile
    const sampledProfile = sampleCompleteProfile(partial, random);

    // Calculate baseline for this sampled profile
    const projection = calculateBaselineQALYs(sampledProfile);

    qalyResults.push(projection.remainingQALYs);
    leResults.push(projection.remainingLifeExpectancy);

    // Track survival curve data
    for (const point of projection.survivalCurve) {
      if (!survivalByAge.has(point.age)) {
        survivalByAge.set(point.age, { survival: [], qaly: [] });
      }
      const ageData = survivalByAge.get(point.age)!;
      ageData.survival.push(point.survivalProbability);
      ageData.qaly.push(point.expectedQALY);
    }
  }

  // Sort for percentile calculations
  qalyResults.sort((a, b) => a - b);
  leResults.sort((a, b) => a - b);

  // Helper to get percentile from sorted array
  const getPercentile = (arr: number[], p: number) =>
    arr[Math.floor(arr.length * (p / 100))];

  // Build survival curve with uncertainty bands
  const survivalCurve: UncertainBaselineResult["survivalCurve"] = [];
  const ages = Array.from(survivalByAge.keys()).sort((a, b) => a - b);

  for (const age of ages) {
    const data = survivalByAge.get(age)!;
    data.survival.sort((a, b) => a - b);
    data.qaly.sort((a, b) => a - b);

    survivalCurve.push({
      age,
      survivalP50: getPercentile(data.survival, 50),
      survivalP5: getPercentile(data.survival, 5),
      survivalP95: getPercentile(data.survival, 95),
      qalyP50: getPercentile(data.qaly, 50),
      qalyP5: getPercentile(data.qaly, 5),
      qalyP95: getPercentile(data.qaly, 95),
    });
  }

  return {
    pointEstimate: {
      remainingQALYs: pointProjection.remainingQALYs,
      remainingLifeExpectancy: pointProjection.remainingLifeExpectancy,
      expectedDeathAge: pointProjection.expectedDeathAge,
      currentQualityWeight: pointProjection.currentQualityWeight,
    },
    predictionInterval: {
      remainingQALYs: {
        p5: getPercentile(qalyResults, 5),
        p25: getPercentile(qalyResults, 25),
        p50: getPercentile(qalyResults, 50),
        p75: getPercentile(qalyResults, 75),
        p95: getPercentile(qalyResults, 95),
      },
      remainingLifeExpectancy: {
        p5: getPercentile(leResults, 5),
        p25: getPercentile(leResults, 25),
        p50: getPercentile(leResults, 50),
        p75: getPercentile(leResults, 75),
        p95: getPercentile(leResults, 95),
      },
    },
    completeness,
    intervalWidth: {
      qalys: getPercentile(qalyResults, 95) - getPercentile(qalyResults, 5),
      lifeYears: getPercentile(leResults, 95) - getPercentile(leResults, 5),
    },
    nSimulations,
    distribution: {
      qalys: qalyResults,
      lifeYears: leResults,
    },
    survivalCurve,
  };
}

/**
 * Quick calculation for real-time updates (fewer simulations)
 */
export function calculateBaselineQuick(
  partial: PartialProfile
): UncertainBaselineResult {
  return calculateBaselineWithUncertainty(partial, {
    nSimulations: 200, // Fast but rougher
    seed: Date.now(), // Different each time for visual effect
  });
}

/**
 * Format prediction interval for display
 * e.g., "28.5 (22.1 - 34.8)"
 */
export function formatPredictionInterval(
  median: number,
  low: number,
  high: number,
  decimals: number = 1
): string {
  return `${median.toFixed(decimals)} (${low.toFixed(decimals)} - ${high.toFixed(decimals)})`;
}
