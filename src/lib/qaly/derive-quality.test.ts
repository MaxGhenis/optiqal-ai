/**
 * Tests for deriving quality of life effects from mechanism effects
 *
 * Quality effects represent changes in day-to-day functioning and wellbeing,
 * separate from mortality/longevity effects.
 */

import { describe, it, expect } from "vitest";
import type { MechanismEffect } from "./types";
import { deriveQualityFromMechanisms, deriveQualityWithBreakdown } from "./derive-quality";

describe("deriveQualityFromMechanisms", () => {
  it("should derive non-zero quality effect from adiposity reduction", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 15, sd: 5 }, // 15% body fat reduction
        evidenceQuality: "strong",
        units: "%",
      },
    ];

    const result = deriveQualityFromMechanisms(mechanisms);

    // Adiposity reduction should improve quality of life (positive utility delta)
    expect(result).not.toBeNull();
    expect(result!.subjectiveWellbeing).not.toBeNull();
    if (result!.subjectiveWellbeing?.type === "normal") {
      expect(result!.subjectiveWellbeing.mean).toBeGreaterThan(0);
    }
  });

  it("should return null when no mechanisms affect quality", () => {
    const mechanisms: MechanismEffect[] = [];
    const result = deriveQualityFromMechanisms(mechanisms);
    expect(result).toBeNull();
  });

  it("should combine multiple mechanism effects on quality", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 10, sd: 3 }, // 10% body fat reduction
        evidenceQuality: "strong",
        units: "%",
      },
      {
        mechanism: "insulin_sensitivity",
        direction: "increase",
        effectSize: { type: "normal", mean: 20, sd: 8 }, // 20% improvement
        evidenceQuality: "moderate",
        units: "%",
      },
      {
        mechanism: "systemic_inflammation",
        direction: "decrease",
        effectSize: { type: "normal", mean: 25, sd: 10 }, // 25% CRP reduction
        evidenceQuality: "moderate",
        units: "%",
      },
    ];

    const result = deriveQualityFromMechanisms(mechanisms);

    expect(result).not.toBeNull();
    // Combined effect should be stronger than single mechanism
    if (result!.subjectiveWellbeing?.type === "normal") {
      expect(result!.subjectiveWellbeing.mean).toBeGreaterThan(0.01);
    }
  });

  it("should handle harmful direction (increases in bad mechanisms)", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "increase",
        effectSize: { type: "normal", mean: 10, sd: 3 }, // 10% body fat increase
        evidenceQuality: "strong",
        units: "%",
      },
    ];

    const result = deriveQualityFromMechanisms(mechanisms);

    expect(result).not.toBeNull();
    // Adiposity increase should decrease quality of life (negative utility delta)
    if (result!.subjectiveWellbeing?.type === "normal") {
      expect(result!.subjectiveWellbeing.mean).toBeLessThan(0);
    }
  });

  it("should widen uncertainty for weak evidence", () => {
    const strongEvidence: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 10, sd: 3 },
        evidenceQuality: "strong",
      },
    ];

    const weakEvidence: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 10, sd: 3 },
        evidenceQuality: "weak",
      },
    ];

    const strongResult = deriveQualityFromMechanisms(strongEvidence);
    const weakResult = deriveQualityFromMechanisms(weakEvidence);

    expect(strongResult).not.toBeNull();
    expect(weakResult).not.toBeNull();

    // Weak evidence should have wider uncertainty (larger sd)
    if (
      strongResult!.subjectiveWellbeing?.type === "normal" &&
      weakResult!.subjectiveWellbeing?.type === "normal"
    ) {
      expect(weakResult!.subjectiveWellbeing.sd).toBeGreaterThan(
        strongResult!.subjectiveWellbeing.sd
      );
    }
  });

  it("should handle sleep quality improvements", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "sleep_quality",
        direction: "increase",
        effectSize: { type: "normal", mean: 0.5, sd: 0.2 }, // 0.5 SD improvement
        evidenceQuality: "moderate",
        units: "SD",
      },
    ];

    const result = deriveQualityFromMechanisms(mechanisms);

    expect(result).not.toBeNull();
    // Better sleep should improve quality of life
    if (result!.subjectiveWellbeing?.type === "normal") {
      expect(result!.subjectiveWellbeing.mean).toBeGreaterThan(0);
    }
  });

  it("should handle neuroplasticity improvements (cognitive function)", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "neuroplasticity",
        direction: "increase",
        effectSize: { type: "normal", mean: 0.3, sd: 0.15 }, // 0.3 SD improvement
        evidenceQuality: "moderate",
        units: "SD",
      },
    ];

    const result = deriveQualityFromMechanisms(mechanisms);

    expect(result).not.toBeNull();
    // Better cognitive function should improve quality of life
    if (result!.subjectiveWellbeing?.type === "normal") {
      expect(result!.subjectiveWellbeing.mean).toBeGreaterThan(0);
    }
  });
});

describe("deriveQualityWithBreakdown", () => {
  it("should return per-mechanism contributions", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 15, sd: 5 },
        evidenceQuality: "strong",
        units: "%",
      },
      {
        mechanism: "sleep_quality",
        direction: "increase",
        effectSize: { type: "normal", mean: 0.5, sd: 0.2 },
        evidenceQuality: "moderate",
        units: "SD",
      },
    ];

    const result = deriveQualityWithBreakdown(mechanisms);

    expect(result).not.toBeNull();
    expect(result!.breakdown).toBeDefined();
    expect(result!.breakdown.length).toBe(2);

    // Each breakdown should have mechanism name and contribution
    const adiposityBreakdown = result!.breakdown.find((b) => b.mechanism === "adiposity");
    const sleepBreakdown = result!.breakdown.find((b) => b.mechanism === "sleep_quality");

    expect(adiposityBreakdown).toBeDefined();
    expect(sleepBreakdown).toBeDefined();
    expect(adiposityBreakdown!.utilityDelta).toBeGreaterThan(0); // Beneficial
    expect(sleepBreakdown!.utilityDelta).toBeGreaterThan(0); // Beneficial
  });

  it("should have breakdown sum approximately equal to total", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 10, sd: 3 },
        evidenceQuality: "strong",
      },
      {
        mechanism: "systemic_inflammation",
        direction: "decrease",
        effectSize: { type: "normal", mean: 20, sd: 8 },
        evidenceQuality: "moderate",
      },
    ];

    const result = deriveQualityWithBreakdown(mechanisms);

    expect(result).not.toBeNull();

    // Sum of breakdown deltas should approximately equal total mean
    const breakdownSum = result!.breakdown.reduce((sum, b) => sum + b.utilityDelta, 0);
    if (result!.combined.subjectiveWellbeing?.type === "normal") {
      expect(breakdownSum).toBeCloseTo(result!.combined.subjectiveWellbeing.mean, 4);
    }
  });

  it("should include causal fraction per mechanism", () => {
    const mechanisms: MechanismEffect[] = [
      {
        mechanism: "adiposity",
        direction: "decrease",
        effectSize: { type: "normal", mean: 10, sd: 3 },
        evidenceQuality: "strong",
      },
      {
        mechanism: "sleep_quality",
        direction: "increase",
        effectSize: { type: "normal", mean: 0.5, sd: 0.2 },
        evidenceQuality: "weak",
      },
    ];

    const result = deriveQualityWithBreakdown(mechanisms);

    expect(result).not.toBeNull();

    const strongMech = result!.breakdown.find((b) => b.mechanism === "adiposity");
    const weakMech = result!.breakdown.find((b) => b.mechanism === "sleep_quality");

    // Strong evidence should have higher causal fraction
    expect(strongMech!.causalFraction).toBeGreaterThan(weakMech!.causalFraction);
  });
});
