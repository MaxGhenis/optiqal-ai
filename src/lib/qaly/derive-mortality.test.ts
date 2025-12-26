/**
 * Tests for deriving mortality effects from mechanism effects
 *
 * Bug: When Claude returns mechanism effects (e.g., improved blood_pressure)
 * but no directMortalityEffect, the simulation returns 0 QALYs because
 * the mechanism→condition→mortality mapping is never applied.
 */

import { describe, it, expect } from "vitest";
import type { MechanismEffect } from "./types";
import { deriveMortalityFromMechanisms, deriveMortalityWithBreakdown } from "./derive-mortality";

describe("deriveMortalityFromMechanisms", () => {
  it("should derive non-zero mortality HR from blood pressure reduction", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "blood_pressure",
        direction: "decrease",
        effectSize: { type: "normal", mean: 5, sd: 2 }, // 5 mmHg reduction
        evidenceQuality: "strong",
        units: "mmHg",
      },
    ];

    const result = deriveMortalityFromMechanisms(mechanisms);

    // Blood pressure reduction should decrease mortality (HR < 1)
    expect(result).not.toBeNull();
    expect(result!.hazardRatio.type).toBe("lognormal");

    // Log-mean should be negative (HR < 1 = beneficial)
    if (result!.hazardRatio.type === "lognormal") {
      expect(result!.hazardRatio.logMean).toBeLessThan(0);
    }
  });

  it("should return null when no mechanisms affect mortality", () => {
    const mechanisms: MechanismEffect[] = [];
    const result = deriveMortalityFromMechanisms(mechanisms);
    expect(result).toBeNull();
  });

  it("should combine multiple mechanism effects", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "blood_pressure",
        direction: "decrease",
        effectSize: { type: "normal", mean: 5, sd: 2 }, // 5 mmHg reduction
        evidenceQuality: "strong",
        units: "mmHg",
      },
      {
        mechanism: "systemic_inflammation",
        direction: "decrease",
        effectSize: { type: "normal", mean: 15, sd: 8 }, // 15% CRP reduction
        evidenceQuality: "moderate",
        units: "%",
      },
    ];

    const result = deriveMortalityFromMechanisms(mechanisms);

    expect(result).not.toBeNull();
    // Combined effect should be stronger than single mechanism
    if (result!.hazardRatio.type === "lognormal") {
      expect(result!.hazardRatio.logMean).toBeLessThan(-0.01);
    }
  });

  it("should handle harmful direction (increases in bad mechanisms)", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "blood_pressure",
        direction: "increase",
        effectSize: { type: "normal", mean: 10, sd: 3 }, // 10 mmHg increase
        evidenceQuality: "strong",
        units: "mmHg",
      },
    ];

    const result = deriveMortalityFromMechanisms(mechanisms);

    expect(result).not.toBeNull();
    // Blood pressure increase should increase mortality (HR > 1)
    if (result!.hazardRatio.type === "lognormal") {
      expect(result!.hazardRatio.logMean).toBeGreaterThan(0);
    }
  });

  it("should widen uncertainty for weak evidence", () => {
    const strongEvidence: MechanismEffect[] = [
      {
        mechanism: "blood_pressure",
        direction: "decrease",
        effectSize: { type: "normal", mean: 5, sd: 2 },
        evidenceQuality: "strong",
      },
    ];

    const weakEvidence: MechanismEffect[] = [
      {
        mechanism: "blood_pressure",
        direction: "decrease",
        effectSize: { type: "normal", mean: 5, sd: 2 },
        evidenceQuality: "weak",
      },
    ];

    const strongResult = deriveMortalityFromMechanisms(strongEvidence);
    const weakResult = deriveMortalityFromMechanisms(weakEvidence);

    expect(strongResult).not.toBeNull();
    expect(weakResult).not.toBeNull();

    // Weak evidence should have wider uncertainty (larger logSd)
    if (
      strongResult!.hazardRatio.type === "lognormal" &&
      weakResult!.hazardRatio.type === "lognormal"
    ) {
      expect(weakResult!.hazardRatio.logSd).toBeGreaterThan(
        strongResult!.hazardRatio.logSd
      );
    }
  });
});

describe("deriveMortalityWithBreakdown", () => {
  it("should return per-mechanism contributions", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "blood_pressure",
        direction: "decrease",
        effectSize: { type: "normal", mean: 5, sd: 2 },
        evidenceQuality: "strong",
        units: "mmHg",
      },
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 15, sd: 5 },
        evidenceQuality: "strong",
        units: "%",
      },
    ];

    const result = deriveMortalityWithBreakdown(mechanisms);

    expect(result).not.toBeNull();
    expect(result!.breakdown).toBeDefined();
    expect(result!.breakdown.length).toBe(2);

    // Each breakdown should have mechanism name and contribution
    const bpBreakdown = result!.breakdown.find((b) => b.mechanism === "blood_pressure");
    const adiposityBreakdown = result!.breakdown.find((b) => b.mechanism === "adiposity");

    expect(bpBreakdown).toBeDefined();
    expect(adiposityBreakdown).toBeDefined();
    expect(bpBreakdown!.logHR).toBeLessThan(0); // Beneficial
    expect(adiposityBreakdown!.logHR).toBeLessThan(0); // Beneficial
  });

  it("should have breakdown sum approximately equal to total", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "blood_pressure",
        direction: "decrease",
        effectSize: { type: "normal", mean: 5, sd: 2 },
        evidenceQuality: "strong",
      },
      {
        mechanism: "systemic_inflammation",
        direction: "decrease",
        effectSize: { type: "normal", mean: 20, sd: 8 },
        evidenceQuality: "moderate",
      },
    ];

    const result = deriveMortalityWithBreakdown(mechanisms);

    expect(result).not.toBeNull();

    // Sum of breakdown logHRs should approximately equal total logMean
    const breakdownSum = result!.breakdown.reduce((sum, b) => sum + b.logHR, 0);
    if (result!.combined.hazardRatio.type === "lognormal") {
      expect(breakdownSum).toBeCloseTo(result!.combined.hazardRatio.logMean, 1);
    }
  });
});
