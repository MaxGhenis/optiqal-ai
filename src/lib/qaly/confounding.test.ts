/**
 * Tests for confounding adjustment module
 */

import { describe, it, expect } from "vitest";
import {
  CONFOUNDING_BY_CATEGORY,
  getConfoundingConfig,
  getExpectedCausalFraction,
  getCausalFractionCI,
  adjustHazardRatio,
  calculateEValue,
  calculateEValueForCI,
  analyzeConfounding,
} from "./confounding";

describe("CONFOUNDING_BY_CATEGORY", () => {
  it("should have expected categories", () => {
    expect(Object.keys(CONFOUNDING_BY_CATEGORY)).toContain("exercise");
    expect(Object.keys(CONFOUNDING_BY_CATEGORY)).toContain("diet");
    expect(Object.keys(CONFOUNDING_BY_CATEGORY)).toContain("sleep");
    expect(Object.keys(CONFOUNDING_BY_CATEGORY)).toContain("medical");
  });

  it("should have valid Beta priors (alpha, beta > 0)", () => {
    for (const [category, config] of Object.entries(CONFOUNDING_BY_CATEGORY)) {
      expect(config.causalFraction.alpha).toBeGreaterThan(0);
      expect(config.causalFraction.beta).toBeGreaterThan(0);
    }
  });

  it("should have medical with highest expected causal fraction", () => {
    const exerciseCausal = getExpectedCausalFraction(CONFOUNDING_BY_CATEGORY.exercise);
    const medicalCausal = getExpectedCausalFraction(CONFOUNDING_BY_CATEGORY.medical);
    expect(medicalCausal).toBeGreaterThan(exerciseCausal);
  });
});

describe("getExpectedCausalFraction", () => {
  it("should return mean of Beta distribution", () => {
    const config = { causalFraction: { alpha: 2, beta: 4 }, rationale: "", calibrationSources: [] };
    expect(getExpectedCausalFraction(config)).toBeCloseTo(2 / 6, 4);
  });

  it("should return ~0.33 for exercise", () => {
    const expected = getExpectedCausalFraction(CONFOUNDING_BY_CATEGORY.exercise);
    expect(expected).toBeCloseTo(0.33, 1);
  });

  it("should return ~0.57 for medical", () => {
    const expected = getExpectedCausalFraction(CONFOUNDING_BY_CATEGORY.medical);
    expect(expected).toBeCloseTo(0.57, 1);
  });
});

describe("getCausalFractionCI", () => {
  it("should return valid 95% CI", () => {
    const ci = getCausalFractionCI(CONFOUNDING_BY_CATEGORY.exercise);
    expect(ci.low).toBeGreaterThanOrEqual(0);
    expect(ci.high).toBeLessThanOrEqual(1);
    expect(ci.low).toBeLessThan(ci.high);
  });

  it("should have CI contain the mean", () => {
    const config = CONFOUNDING_BY_CATEGORY.diet;
    const mean = getExpectedCausalFraction(config);
    const ci = getCausalFractionCI(config);
    expect(ci.low).toBeLessThan(mean);
    expect(ci.high).toBeGreaterThan(mean);
  });
});

describe("adjustHazardRatio", () => {
  it("should return 1 when causal fraction is 0", () => {
    expect(adjustHazardRatio(0.8, 0)).toBeCloseTo(1, 4);
  });

  it("should return original HR when causal fraction is 1", () => {
    expect(adjustHazardRatio(0.8, 1)).toBeCloseTo(0.8, 4);
  });

  it("should shrink protective effect toward 1", () => {
    const observedHR = 0.78;
    const adjustedHR = adjustHazardRatio(observedHR, 0.33);
    expect(adjustedHR).toBeGreaterThan(observedHR);
    expect(adjustedHR).toBeLessThan(1);
  });

  it("should shrink harmful effect toward 1", () => {
    const observedHR = 1.5;
    const adjustedHR = adjustHazardRatio(observedHR, 0.33);
    expect(adjustedHR).toBeLessThan(observedHR);
    expect(adjustedHR).toBeGreaterThan(1);
  });

  it("should match whatnut example: HR 0.78 with 25% causal", () => {
    // From whatnut appendix: Beta(1.5, 4.5) → mean 0.25
    const observedHR = 0.78;
    const adjustedHR = adjustHazardRatio(observedHR, 0.25);
    // log(0.78) = -0.248, × 0.25 = -0.062, exp = 0.94
    expect(adjustedHR).toBeCloseTo(0.94, 2);
  });
});

describe("calculateEValue", () => {
  it("should calculate E-value for protective effect", () => {
    // HR = 0.78 → RR = 1/0.78 = 1.28
    // E-value = 1.28 + sqrt(1.28 × 0.28) ≈ 1.88
    const result = calculateEValue(0.78);
    expect(result.eValue).toBeCloseTo(1.88, 1);
  });

  it("should calculate E-value for harmful effect", () => {
    // HR = 1.5
    // E-value = 1.5 + sqrt(1.5 × 0.5) ≈ 2.37
    const result = calculateEValue(1.5);
    expect(result.eValue).toBeCloseTo(2.37, 1);
  });

  it("should return E-value of 1 when HR = 1", () => {
    const result = calculateEValue(1.0);
    expect(result.eValue).toBeCloseTo(1, 4);
  });

  it("should return interpretation for weak effects", () => {
    const result = calculateEValue(0.95);
    expect(result.interpretation.toLowerCase()).toContain("susceptible");
  });

  it("should return interpretation for robust effects", () => {
    const result = calculateEValue(0.5);
    expect(result.interpretation.toLowerCase()).toContain("robust");
  });
});

describe("calculateEValueForCI", () => {
  it("should calculate E-values for point and CI", () => {
    const result = calculateEValueForCI(0.78, 0.71, 0.85);
    expect(result.eValuePoint).toBeGreaterThan(1);
    expect(result.eValueCI).toBeGreaterThan(1);
    expect(result.eValuePoint).toBeGreaterThan(result.eValueCI);
  });

  it("should flag when CI has low E-value", () => {
    // CI bound close to null has low E-value
    const result = calculateEValueForCI(0.90, 0.85, 1.02);
    // For RR = 1.02: E-value = 1.02 + sqrt(1.02 × 0.02) ≈ 1.16
    expect(result.eValueCI).toBeLessThan(1.2);
    expect(result.interpretation.toLowerCase()).toContain("weak confounding");
  });
});

describe("analyzeConfounding", () => {
  it("should return full confounding analysis", () => {
    const analysis = analyzeConfounding("exercise", 0.84, "meta-analysis");

    expect(analysis.category).toBe("exercise");
    expect(analysis.evidenceType).toBe("meta-analysis");
    expect(analysis.expectedCausalFraction).toBeGreaterThan(0);
    expect(analysis.expectedCausalFraction).toBeLessThan(1);
    expect(analysis.eValue.point).toBeGreaterThan(1);
    expect(analysis.adjustedHR.original).toBe(0.84);
    expect(analysis.adjustedHR.adjusted).toBeGreaterThan(0.84);
    expect(analysis.adjustedHR.percentReduction).toBeGreaterThan(0);
  });

  it("should give higher causal fraction for RCT vs cohort", () => {
    const rctAnalysis = analyzeConfounding("diet", 0.80, "rct");
    const cohortAnalysis = analyzeConfounding("diet", 0.80, "cohort");

    expect(rctAnalysis.expectedCausalFraction).toBeGreaterThan(cohortAnalysis.expectedCausalFraction);
  });

  it("should adjust HR less for medical interventions", () => {
    const exerciseAnalysis = analyzeConfounding("exercise", 0.80);
    const medicalAnalysis = analyzeConfounding("medical", 0.80);

    // Medical should have smaller adjustment (more causal)
    expect(medicalAnalysis.adjustedHR.percentReduction).toBeLessThan(
      exerciseAnalysis.adjustedHR.percentReduction
    );
  });
});

describe("getConfoundingConfig", () => {
  it("should adjust alpha for RCT evidence", () => {
    const base = getConfoundingConfig("exercise");
    const rct = getConfoundingConfig("exercise", "rct");

    expect(rct.causalFraction.alpha).toBeGreaterThan(base.causalFraction.alpha);
    expect(rct.causalFraction.beta).toBe(base.causalFraction.beta);
  });

  it("should reduce alpha for cohort evidence", () => {
    const base = getConfoundingConfig("diet");
    const cohort = getConfoundingConfig("diet", "cohort");

    expect(cohort.causalFraction.alpha).toBeLessThan(base.causalFraction.alpha);
  });

  it("should fall back to 'other' for unknown category", () => {
    const unknown = getConfoundingConfig("unknown_category" as any);
    expect(unknown.causalFraction.alpha).toBe(CONFOUNDING_BY_CATEGORY.other.causalFraction.alpha);
  });
});
