/**
 * Tests for Monte Carlo QALY simulation with confounding adjustment
 */

import { describe, it, expect } from "vitest";
import { simulateQALYImpact, simulateQALYImpactRigorous } from "./simulate";
import type { InterventionEffect } from "./types";
import type { UserProfile } from "@/types";

// Mock user profile
const mockProfile: UserProfile = {
  age: 40,
  sex: "male",
  height: 178, // cm
  weight: 82, // kg
  smoker: false,
  exerciseHoursPerWeek: 3,
  sleepHoursPerNight: 7,
  existingConditions: [],
  diet: "omnivore",
};

// Mock exercise intervention (walking)
const walkingIntervention: InterventionEffect = {
  description: "Walk 30 minutes daily",
  category: "exercise",
  mechanismEffects: [],
  mortality: {
    hazardRatio: { type: "lognormal", logMean: -0.18, logSd: 0.08 }, // HR ~0.84
    onsetDelay: 0,
    rampUpPeriod: 0.5,
    decayRate: 0,
  },
  quality: null,
  costs: null,
  evidenceQuality: "high",
  keySources: [],
  caveats: [],
  profileAdjustments: [],
};

// Mock medical intervention (less confounding)
const medicalIntervention: InterventionEffect = {
  description: "Statin therapy",
  category: "medical",
  mechanismEffects: [],
  mortality: {
    hazardRatio: { type: "lognormal", logMean: -0.15, logSd: 0.05 }, // HR ~0.86
    onsetDelay: 0.5,
    rampUpPeriod: 1,
    decayRate: 0,
  },
  quality: null,
  costs: null,
  evidenceQuality: "high",
  keySources: [],
  caveats: [],
  profileAdjustments: [],
};

describe("simulateQALYImpact with confounding", () => {
  it("should return confounding result when confounding is applied", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
    });

    expect(result.confounding).toBeDefined();
    expect(result.confounding?.applied).toBe(true);
    expect(result.confounding?.expectedCausalFraction).toBeGreaterThan(0);
    expect(result.confounding?.expectedCausalFraction).toBeLessThan(1);
  });

  it("should not return confounding result when disabled", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: false,
    });

    expect(result.confounding).toBeUndefined();
  });

  it("should have lower QALY estimate with confounding adjustment", () => {
    const withConfounding = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 2000,
      applyConfounding: true,
    });

    const withoutConfounding = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 2000,
      applyConfounding: false,
    });

    // Confounding-adjusted estimate should be lower (effect is shrunk toward null)
    expect(withConfounding.median).toBeLessThan(withoutConfounding.median);
  });

  it("should apply less adjustment for medical interventions than exercise", () => {
    const exerciseResult = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
    });

    const medicalResult = simulateQALYImpact(mockProfile, medicalIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
    });

    // Medical should have higher causal fraction (less confounding)
    expect(medicalResult.confounding?.expectedCausalFraction).toBeGreaterThan(
      exerciseResult.confounding?.expectedCausalFraction || 0
    );
  });

  it("should include E-value in confounding result", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
    });

    expect(result.confounding?.eValue.point).toBeGreaterThan(1);
    expect(result.confounding?.eValue.interpretation).toBeDefined();
  });

  it("should show reduction in estimate due to confounding", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 2000,
      applyConfounding: true,
    });

    // Should show a positive reduction percentage
    expect(result.confounding?.comparison.reductionPercent).toBeGreaterThan(0);
    // Unadjusted should be higher than adjusted
    expect(result.confounding?.comparison.unadjustedMedian).toBeGreaterThan(
      result.confounding?.comparison.adjustedMedian || 0
    );
  });

  it("should accept evidence type for confounding adjustment", () => {
    const rctResult = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
      evidenceType: "rct",
    });

    const cohortResult = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
      evidenceType: "cohort",
    });

    // RCT evidence should have higher causal fraction than cohort
    expect(rctResult.confounding?.expectedCausalFraction).toBeGreaterThan(
      cohortResult.confounding?.expectedCausalFraction || 0
    );
  });

  it("should accept confounding override", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
      confoundingOverride: { alpha: 5, beta: 5 }, // 50% causal
    });

    expect(result.confounding?.expectedCausalFraction).toBeCloseTo(0.5, 1);
  });

  it("should return valid credible interval for causal fraction", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: true,
    });

    const ci = result.confounding?.causalFractionCI;
    expect(ci?.low).toBeGreaterThanOrEqual(0);
    expect(ci?.high).toBeLessThanOrEqual(1);
    expect(ci?.low).toBeLessThan(ci?.high || 0);
  });
});

describe("simulateQALYImpact basic functionality", () => {
  it("should return positive QALY gain for beneficial intervention", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      applyConfounding: false,
    });

    expect(result.median).toBeGreaterThan(0);
    expect(result.probPositive).toBeGreaterThan(0.5);
  });

  it("should return valid percentiles", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
    });

    expect(result.percentiles).toHaveLength(9);
    // Percentiles should be monotonically increasing
    for (let i = 1; i < result.percentiles.length; i++) {
      expect(result.percentiles[i].value).toBeGreaterThanOrEqual(
        result.percentiles[i - 1].value
      );
    }
  });

  it("should have CI95 contain median", () => {
    const result = simulateQALYImpact(mockProfile, walkingIntervention, {
      nSimulations: 1000,
    });

    expect(result.ci95.low).toBeLessThanOrEqual(result.median);
    expect(result.ci95.high).toBeGreaterThanOrEqual(result.median);
  });
});

describe("simulateQALYImpactRigorous", () => {
  it("should use lifecycle model by default", () => {
    const result = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 1000,
    });

    expect(result.lifecycle.used).toBe(true);
    expect(result.lifecycle.discountRate).toBe(0.03);
  });

  it("should return pathway contributions", () => {
    const result = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 1000,
    });

    expect(result.lifecycle.pathwayContributions.cvd.median).toBeGreaterThanOrEqual(0);
    expect(result.lifecycle.pathwayContributions.cancer.median).toBeGreaterThanOrEqual(0);
    expect(result.lifecycle.pathwayContributions.other.median).toBeGreaterThanOrEqual(0);
  });

  it("should return life years gained", () => {
    const result = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 1000,
    });

    expect(result.lifecycle.lifeYearsGained.median).toBeGreaterThan(0);
  });

  it("should respect custom discount rate", () => {
    const discounted = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      discountRate: 0.03,
    });

    const undiscounted = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      discountRate: 0,
    });

    expect(discounted.median).toBeLessThan(undiscounted.median);
    expect(discounted.lifecycle.discountRate).toBe(0.03);
    expect(undiscounted.lifecycle.discountRate).toBe(0);
  });

  it("should give results in whatnut range", () => {
    // Whatnut: ~0.11-0.20 discounted QALYs for daily nut consumption
    // Walking should be in similar range with confounding adjustment
    const result = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 2000,
      applyConfounding: true,
    });

    // Should be positive but modest after confounding adjustment
    expect(result.median).toBeGreaterThan(0.01);
    expect(result.median).toBeLessThan(1.0);
  });

  it("should fall back to basic simulation when lifecycle disabled", () => {
    const result = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      useLifecycleModel: false,
    });

    expect(result.lifecycle.used).toBe(false);
  });

  it("should accept custom pathway HRs", () => {
    const result = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 1000,
      pathwayHRs: {
        cvd: 0.75,
        cancer: 0.90,
        other: 0.95,
      },
    });

    expect(result.lifecycle.used).toBe(true);
    // CVD contribution should be largest with these HRs
    expect(result.lifecycle.pathwayContributions.cvd.median).toBeGreaterThan(
      result.lifecycle.pathwayContributions.other.median
    );
  });

  it("should return non-zero qualityQALYs when quality effect is provided", () => {
    // Intervention with quality effect (e.g., Ozempic improves mobility)
    const interventionWithQuality: InterventionEffect = {
      ...walkingIntervention,
      quality: {
        conditionEffects: [],
        directDimensionEffects: [],
        subjectiveWellbeing: {
          type: "normal",
          mean: 0.03, // 3% utility improvement
          sd: 0.01,
        },
        onsetDelay: 0,
        decayRate: 0,
      },
    };

    const result = simulateQALYImpactRigorous(mockProfile, interventionWithQuality, {
      nSimulations: 1000,
    });

    // Quality QALYs should be non-zero
    expect(result.breakdown.qualityQALYs.median).toBeGreaterThan(0);
  });

  it("should widen CI for low evidence quality (not change point estimate)", () => {
    // High quality evidence
    const highQuality = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 5000,
      evidenceQuality: "high",
    });

    // Low quality evidence - should have wider CI, similar median
    const lowQuality = simulateQALYImpactRigorous(mockProfile, walkingIntervention, {
      nSimulations: 5000,
      evidenceQuality: "low",
    });

    // Medians should be similar (within 50%)
    const medianRatio = lowQuality.median / highQuality.median;
    expect(medianRatio).toBeGreaterThan(0.5);
    expect(medianRatio).toBeLessThan(1.5);

    // CI width should be larger for low quality
    const highCIWidth = highQuality.ci95.high - highQuality.ci95.low;
    const lowCIWidth = lowQuality.ci95.high - lowQuality.ci95.low;
    expect(lowCIWidth).toBeGreaterThan(highCIWidth * 1.2); // At least 20% wider
  });
});
