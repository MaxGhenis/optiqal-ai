/**
 * Tests for share/export functionality
 */

import { describe, it, expect } from "vitest";
import { formatAnalysisForExport, formatAnalysisForPDF } from "./share";
import type { StructuredAnalysisResult } from "./analyze-structured";
import type { UserProfile } from "@/types";

// Mock analysis result for testing
const mockProfile: UserProfile = {
  age: 40,
  sex: "male",
  height: 178,
  weight: 82,
  smoker: false,
  exerciseHoursPerWeek: 3,
  sleepHoursPerNight: 7,
  existingConditions: [],
  diet: "omnivore",
};

const mockResult: StructuredAnalysisResult = {
  intervention: "Walk 30 minutes daily",
  counterfactual: "no additional walking",
  profile: mockProfile,
  source: {
    type: "precomputed",
    precomputedId: "walking",
    precomputedName: "Daily Walking",
    confidence: 0.95,
  },
  baseline: {
    remainingLifeExpectancy: 42.5,
    remainingQALYs: 35.2,
  },
  mechanismEffects: [
    {
      mechanism: "blood_pressure",
      effectSize: { type: "normal", mean: 5, sd: 2 },
      direction: "decrease",
      units: "mmHg",
      evidenceQuality: "strong",
    },
  ],
  simulation: {
    median: 0.25,
    mean: 0.26,
    sd: 0.12,
    ci95: { low: 0.05, high: 0.48 },
    ci90: { low: 0.08, high: 0.45 },
    percentiles: [],
    probPositive: 0.92,
    probMoreThanOneYear: 0.15,
    nSimulations: 10000,
    breakdown: {
      mortalityQALYs: { median: 0.18, ci95: { low: 0.03, high: 0.35 } },
      qualityQALYs: { median: 0.07, ci95: { low: 0.01, high: 0.15 } },
      costQALYs: { median: 0, ci95: { low: 0, high: 0 } },
    },
    confounding: {
      applied: true,
      expectedCausalFraction: 0.6,
      causalFractionCI: { low: 0.45, high: 0.75 },
      eValue: {
        point: 2.1,
        ciLow: 1.5,
        interpretation: "Moderate robustness to unmeasured confounding",
      },
      comparison: {
        unadjustedMedian: 0.42,
        adjustedMedian: 0.25,
        reductionPercent: 40,
      },
    },
    lifecycle: {
      used: true,
      discountRate: 0.03,
      pathwayContributions: {
        cvd: { median: 0.12, ci95: { low: 0.02, high: 0.25 } },
        cancer: { median: 0.04, ci95: { low: 0.01, high: 0.08 } },
        other: { median: 0.02, ci95: { low: 0.00, high: 0.05 } },
      },
      lifeYearsGained: { median: 0.35, ci95: { low: 0.05, high: 0.70 } },
    },
  },
  summary: {
    totalQALYs: { median: 0.25, ci95Low: 0.05, ci95High: 0.48 },
    totalMinutes: { median: 131400, ci95Low: 26280, ci95High: 252288 },
    probPositive: 0.92,
    confidenceLevel: "high",
  },
  evidence: {
    quality: "high",
    keyStudies: [
      {
        citation: "Smith et al. 2023",
        studyType: "meta-analysis",
        relevance: "Effect on cardiovascular outcomes",
      },
    ],
    caveats: [
      "Effects may vary based on baseline activity level",
      "Assumes consistent adherence",
    ],
  },
  affectedMechanisms: [
    {
      mechanism: "blood_pressure",
      direction: "decrease",
      evidenceQuality: "strong",
      affectedConditions: ["hypertension", "cardiovascular disease"],
      effectSize: { type: "normal", mean: 5, sd: 2 },
      units: "mmHg",
    },
  ],
};

describe("formatAnalysisForExport", () => {
  it("should include intervention name", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("Walk 30 minutes daily");
  });

  it("should include counterfactual", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("no additional walking");
  });

  it("should include QALY impact with median and CI", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("+3.0 months"); // 0.25 years formatted
    expect(text).toContain("95% CI:");
    expect(text).toContain("+18.3 days"); // 0.05 years formatted
    expect(text).toContain("+5.8 months"); // 0.48 years formatted
  });

  it("should include mechanism breakdown", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("blood pressure"); // formatted with space
    expect(text).toContain("decrease");
  });

  it("should include evidence quality", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("high");
  });

  it("should include key studies", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("Smith et al. 2023");
  });

  it("should include caveats", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("Effects may vary based on baseline activity level");
    expect(text).toContain("Assumes consistent adherence");
  });

  it("should include disclaimer", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("should not be considered medical advice");
    expect(text).toContain("consult healthcare professionals");
  });

  it("should format longevity and quality breakdown separately", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("Longevity:");
    expect(text).toContain("Quality:");
    expect(text).toContain("+2.2 months"); // 0.18 years formatted
    expect(text).toContain("+25.6 days"); // 0.07 years formatted
  });

  it("should include confounding adjustment details", () => {
    const text = formatAnalysisForExport(mockResult);
    expect(text).toContain("confounding");
    expect(text).toContain("60%");
  });

  it("should handle result without confounding", () => {
    const resultWithoutConfounding = {
      ...mockResult,
      simulation: {
        ...mockResult.simulation,
        confounding: undefined,
      },
    };
    const text = formatAnalysisForExport(resultWithoutConfounding);
    expect(text).toBeTruthy();
    expect(text).toContain("Walk 30 minutes daily");
  });
});

describe("formatAnalysisForPDF", () => {
  it("should return structured data for PDF generation", () => {
    const data = formatAnalysisForPDF(mockResult);

    expect(data.title).toBe("Walk 30 minutes daily");
    expect(data.subtitle).toContain("no additional walking");
    expect(data.qalyImpact).toBe("+3.0 months"); // 0.25 years formatted
    expect(data.confidenceInterval).toContain("18.3 days"); // 0.05 years formatted
    expect(data.confidenceInterval).toContain("5.8 months"); // 0.48 years formatted
  });

  it("should include sections with proper structure", () => {
    const data = formatAnalysisForPDF(mockResult);

    expect(data.sections).toHaveLength(4);
    expect(data.sections[0].title).toBe("QALY Impact");
    expect(data.sections[1].title).toBe("Breakdown");
    expect(data.sections[2].title).toBe("Evidence");
    expect(data.sections[3].title).toBe("Important Notes");
  });

  it("should format breakdown section correctly", () => {
    const data = formatAnalysisForPDF(mockResult);
    const breakdownSection = data.sections.find(s => s.title === "Breakdown");

    expect(breakdownSection).toBeDefined();
    expect(breakdownSection?.items).toContain("Longevity: +2.2 months (95% CI: +10.9 days to +4.2 months)");
    expect(breakdownSection?.items).toContain("Quality: +25.6 days (95% CI: +87.6 hours to +1.8 months)");
  });

  it("should include mechanisms in evidence section", () => {
    const data = formatAnalysisForPDF(mockResult);
    const evidenceSection = data.sections.find(s => s.title === "Evidence");

    expect(evidenceSection).toBeDefined();
    expect(evidenceSection?.items.some(item => item.includes("blood pressure"))).toBe(true); // formatted with space
  });

  it("should include disclaimer", () => {
    const data = formatAnalysisForPDF(mockResult);

    expect(data.disclaimer).toBeDefined();
    expect(data.disclaimer).toContain("should not be considered medical advice");
  });
});
