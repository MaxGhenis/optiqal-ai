/**
 * Tests for rigorous lifecycle QALY model
 *
 * Based on whatnut methodology:
 * - CDC life tables for survival curves
 * - Pathway decomposition (CVD, cancer, other)
 * - Age-varying cause fractions
 * - 3% annual discounting
 */

import { describe, it, expect } from "vitest";
import {
  CDC_LIFE_TABLE,
  getSurvivalProbability,
  getAnnualMortalityRate,
  CAUSE_FRACTIONS,
  getCauseFraction,
  applyDiscount,
  getDiscountedQALY,
  calculateLifecycleQALYs,
  type LifecycleResult,
} from "./lifecycle";

describe("CDC Life Tables", () => {
  it("should have mortality rates for ages 0-100", () => {
    expect(CDC_LIFE_TABLE.male[0]).toBeDefined();
    expect(CDC_LIFE_TABLE.male[40]).toBeDefined();
    expect(CDC_LIFE_TABLE.male[85]).toBeDefined();
    expect(CDC_LIFE_TABLE.female[0]).toBeDefined();
    expect(CDC_LIFE_TABLE.female[40]).toBeDefined();
  });

  it("should have increasing mortality rates with age", () => {
    expect(getAnnualMortalityRate(60, "male")).toBeGreaterThan(
      getAnnualMortalityRate(40, "male")
    );
    expect(getAnnualMortalityRate(80, "female")).toBeGreaterThan(
      getAnnualMortalityRate(60, "female")
    );
  });

  it("should have higher male mortality at most ages", () => {
    expect(getAnnualMortalityRate(50, "male")).toBeGreaterThan(
      getAnnualMortalityRate(50, "female")
    );
  });
});

describe("getSurvivalProbability", () => {
  it("should return 1.0 at current age", () => {
    expect(getSurvivalProbability(40, 40, "male")).toBe(1.0);
  });

  it("should decrease with age", () => {
    const p50 = getSurvivalProbability(40, 50, "male");
    const p60 = getSurvivalProbability(40, 60, "male");
    const p70 = getSurvivalProbability(40, 70, "male");

    expect(p50).toBeLessThan(1.0);
    expect(p60).toBeLessThan(p50);
    expect(p70).toBeLessThan(p60);
  });

  it("should approach 0 at very old ages", () => {
    const p100 = getSurvivalProbability(40, 100, "male");
    expect(p100).toBeLessThan(0.1);
  });

  it("should give reasonable life expectancy", () => {
    // 40-year-old male should have ~50% survival to ~78
    const p78 = getSurvivalProbability(40, 78, "male");
    expect(p78).toBeGreaterThan(0.4);
    expect(p78).toBeLessThan(0.6);
  });
});

describe("Cause of Death Fractions", () => {
  it("should have fractions for CVD, cancer, other", () => {
    const fractions = getCauseFraction(50);
    expect(fractions.cvd).toBeDefined();
    expect(fractions.cancer).toBeDefined();
    expect(fractions.other).toBeDefined();
  });

  it("should sum to 1.0", () => {
    for (const age of [40, 50, 60, 70, 80]) {
      const fractions = getCauseFraction(age);
      const sum = fractions.cvd + fractions.cancer + fractions.other;
      expect(sum).toBeCloseTo(1.0, 4);
    }
  });

  it("should show increasing CVD fraction with age", () => {
    const young = getCauseFraction(40);
    const old = getCauseFraction(80);
    expect(old.cvd).toBeGreaterThan(young.cvd);
  });

  it("should show decreasing cancer fraction at very old ages", () => {
    const middle = getCauseFraction(60);
    const veryOld = getCauseFraction(85);
    expect(veryOld.cancer).toBeLessThan(middle.cancer);
  });
});

describe("Discounting", () => {
  it("should return 1.0 for year 0", () => {
    expect(applyDiscount(1.0, 0)).toBe(1.0);
  });

  it("should reduce value over time at 3%", () => {
    const year10 = applyDiscount(1.0, 10);
    const year20 = applyDiscount(1.0, 20);

    // At 3%: 1/(1.03)^10 ≈ 0.744
    expect(year10).toBeCloseTo(0.744, 2);
    // At 3%: 1/(1.03)^20 ≈ 0.554
    expect(year20).toBeCloseTo(0.554, 2);
  });

  it("should be customizable", () => {
    const noDiscount = applyDiscount(1.0, 10, 0);
    const highDiscount = applyDiscount(1.0, 10, 0.05);

    expect(noDiscount).toBe(1.0);
    expect(highDiscount).toBeLessThan(applyDiscount(1.0, 10, 0.03));
  });
});

describe("getDiscountedQALY", () => {
  it("should combine survival, quality, and discounting", () => {
    const qaly = getDiscountedQALY({
      survivalProb: 0.9,
      qualityWeight: 0.85,
      year: 10,
      discountRate: 0.03,
    });

    // Expected: 0.9 × 0.85 × (1/1.03)^10 ≈ 0.569
    expect(qaly).toBeCloseTo(0.569, 2);
  });

  it("should be 0 when survival is 0", () => {
    const qaly = getDiscountedQALY({
      survivalProb: 0,
      qualityWeight: 0.85,
      year: 10,
      discountRate: 0.03,
    });
    expect(qaly).toBe(0);
  });
});

describe("calculateLifecycleQALYs", () => {
  it("should return baseline and intervention QALYs", () => {
    const result = calculateLifecycleQALYs({
      startAge: 40,
      sex: "male",
      pathwayHRs: {
        cvd: 1.0,
        cancer: 1.0,
        other: 1.0,
      },
    });

    expect(result.baselineQALYs).toBeGreaterThan(0);
    expect(result.interventionQALYs).toBeGreaterThan(0);
    expect(result.qalyGain).toBeCloseTo(0, 10); // No intervention effect
  });

  it("should show QALY gain with protective intervention", () => {
    const result = calculateLifecycleQALYs({
      startAge: 40,
      sex: "male",
      pathwayHRs: {
        cvd: 0.75, // 25% reduction in CVD mortality
        cancer: 0.87,
        other: 0.90,
      },
    });

    expect(result.qalyGain).toBeGreaterThan(0);
    expect(result.interventionQALYs).toBeGreaterThan(result.baselineQALYs);
  });

  it("should show larger undiscounted gains for younger starting age", () => {
    // With discounting, near-term gains matter more, so older people
    // can actually gain more discounted QALYs. Test undiscounted instead.
    const young = calculateLifecycleQALYs({
      startAge: 30,
      sex: "male",
      pathwayHRs: { cvd: 0.75, cancer: 0.87, other: 0.90 },
      discountRate: 0, // No discounting
    });

    const old = calculateLifecycleQALYs({
      startAge: 70,
      sex: "male",
      pathwayHRs: { cvd: 0.75, cancer: 0.87, other: 0.90 },
      discountRate: 0, // No discounting
    });

    // Without discounting, younger people gain more total life years
    expect(young.lifeYearsGained).toBeGreaterThan(old.lifeYearsGained);
  });

  it("should return pathway contributions", () => {
    const result = calculateLifecycleQALYs({
      startAge: 40,
      sex: "male",
      pathwayHRs: { cvd: 0.75, cancer: 0.87, other: 0.90 },
    });

    expect(result.pathwayContributions.cvd).toBeGreaterThan(0);
    expect(result.pathwayContributions.cancer).toBeGreaterThan(0);
    expect(result.pathwayContributions.other).toBeGreaterThan(0);

    // CVD has lowest HR (0.75) so should contribute most
    expect(result.pathwayContributions.cvd).toBeGreaterThan(
      result.pathwayContributions.other
    );
  });

  it("should respect discount rate", () => {
    const discounted = calculateLifecycleQALYs({
      startAge: 40,
      sex: "male",
      pathwayHRs: { cvd: 0.75, cancer: 0.87, other: 0.90 },
      discountRate: 0.03,
    });

    const undiscounted = calculateLifecycleQALYs({
      startAge: 40,
      sex: "male",
      pathwayHRs: { cvd: 0.75, cancer: 0.87, other: 0.90 },
      discountRate: 0,
    });

    expect(discounted.qalyGain).toBeLessThan(undiscounted.qalyGain);
  });

  it("should match whatnut approximate values", () => {
    // From whatnut: ~0.11-0.20 discounted QALYs for nut consumption
    // Using similar HRs: CVD 0.75, Cancer 0.87, Other 0.90
    // With 25% causal fraction → adjusted HRs closer to 1
    const result = calculateLifecycleQALYs({
      startAge: 40,
      sex: "male",
      pathwayHRs: {
        cvd: 0.94, // 0.75^0.25 ≈ adjusted for 25% causal
        cancer: 0.97,
        other: 0.97,
      },
      discountRate: 0.03,
    });

    // Should be in rough range of whatnut results
    expect(result.qalyGain).toBeGreaterThan(0.05);
    expect(result.qalyGain).toBeLessThan(0.5);
  });
});
