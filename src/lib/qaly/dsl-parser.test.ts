/**
 * Tests for DSL parser
 */

import { describe, it, expect } from "vitest";
import {
  parseDistribution,
  parseIntervention,
  parseConfounding,
  formatDistribution,
  getDistributionMean,
  getDistributionSD,
  type YAMLIntervention,
} from "./dsl-parser";

describe("parseDistribution", () => {
  describe("shorthand syntax", () => {
    it("should parse Normal(mean, sd)", () => {
      const result = parseDistribution("Normal(-4, 2)");
      expect(result).toEqual({ type: "normal", mean: -4, sd: 2 });
    });

    it("should parse LogNormal(logMean, logSd)", () => {
      const result = parseDistribution("LogNormal(-0.18, 0.08)");
      expect(result).toEqual({ type: "lognormal", logMean: -0.18, logSd: 0.08 });
    });

    it("should parse Beta(alpha, beta)", () => {
      const result = parseDistribution("Beta(2.5, 5.0)");
      expect(result).toEqual({ type: "beta", alpha: 2.5, beta: 5.0 });
    });

    it("should parse Uniform(min, max)", () => {
      const result = parseDistribution("Uniform(0, 1)");
      expect(result).toEqual({ type: "uniform", min: 0, max: 1 });
    });

    it("should parse Point(value)", () => {
      const result = parseDistribution("Point(0.5)");
      expect(result).toEqual({ type: "point", value: 0.5 });
    });

    it("should be case-insensitive", () => {
      expect(parseDistribution("normal(-4, 2)")).toEqual({ type: "normal", mean: -4, sd: 2 });
      expect(parseDistribution("LOGNORMAL(-0.18, 0.08)")).toEqual({ type: "lognormal", logMean: -0.18, logSd: 0.08 });
    });

    it("should handle spaces in arguments", () => {
      const result = parseDistribution("Normal( -4 , 2 )");
      expect(result).toEqual({ type: "normal", mean: -4, sd: 2 });
    });

    it("should throw on invalid format", () => {
      expect(() => parseDistribution("invalid")).toThrow();
      expect(() => parseDistribution("Normal(1)")).toThrow();
      expect(() => parseDistribution("Unknown(1, 2)")).toThrow();
    });
  });

  describe("object syntax", () => {
    it("should parse point distribution", () => {
      const result = parseDistribution({ type: "point", value: 0.5 });
      expect(result).toEqual({ type: "point", value: 0.5 });
    });

    it("should parse normal distribution", () => {
      const result = parseDistribution({ type: "normal", mean: 10, sd: 2 });
      expect(result).toEqual({ type: "normal", mean: 10, sd: 2 });
    });

    it("should convert snake_case to camelCase for lognormal", () => {
      const result = parseDistribution({ type: "lognormal", log_mean: -0.2, log_sd: 0.1 });
      expect(result).toEqual({ type: "lognormal", logMean: -0.2, logSd: 0.1 });
    });

    it("should parse beta distribution", () => {
      const result = parseDistribution({ type: "beta", alpha: 2, beta: 5 });
      expect(result).toEqual({ type: "beta", alpha: 2, beta: 5 });
    });

    it("should parse uniform distribution", () => {
      const result = parseDistribution({ type: "uniform", min: 0, max: 10 });
      expect(result).toEqual({ type: "uniform", min: 0, max: 10 });
    });
  });
});

describe("formatDistribution", () => {
  it("should format point distribution", () => {
    expect(formatDistribution({ type: "point", value: 0.5 })).toBe("0.50");
  });

  it("should format normal distribution", () => {
    expect(formatDistribution({ type: "normal", mean: -4, sd: 2 })).toBe("Normal(-4.00, 2.00)");
  });

  it("should format lognormal distribution", () => {
    expect(formatDistribution({ type: "lognormal", logMean: -0.18, logSd: 0.08 })).toBe("LogNormal(-0.18, 0.08)");
  });

  it("should format beta distribution", () => {
    expect(formatDistribution({ type: "beta", alpha: 2.5, beta: 5.0 })).toBe("Beta(2.5, 5.0)");
  });

  it("should format uniform distribution", () => {
    expect(formatDistribution({ type: "uniform", min: 0, max: 1 })).toBe("Uniform(0.00, 1.00)");
  });
});

describe("getDistributionMean", () => {
  it("should return value for point", () => {
    expect(getDistributionMean({ type: "point", value: 5 })).toBe(5);
  });

  it("should return mean for normal", () => {
    expect(getDistributionMean({ type: "normal", mean: 10, sd: 2 })).toBe(10);
  });

  it("should calculate mean for lognormal", () => {
    // E[X] = exp(μ + σ²/2) for lognormal
    const result = getDistributionMean({ type: "lognormal", logMean: 0, logSd: 1 });
    expect(result).toBeCloseTo(Math.exp(0.5), 4);
  });

  it("should calculate mean for beta", () => {
    // E[X] = α/(α+β)
    expect(getDistributionMean({ type: "beta", alpha: 2, beta: 4 })).toBeCloseTo(1/3, 4);
  });

  it("should calculate mean for uniform", () => {
    expect(getDistributionMean({ type: "uniform", min: 0, max: 10 })).toBe(5);
  });
});

describe("getDistributionSD", () => {
  it("should return 0 for point", () => {
    expect(getDistributionSD({ type: "point", value: 5 })).toBe(0);
  });

  it("should return sd for normal", () => {
    expect(getDistributionSD({ type: "normal", mean: 10, sd: 2 })).toBe(2);
  });

  it("should calculate SD for beta", () => {
    // SD = sqrt(αβ / ((α+β)² × (α+β+1)))
    const result = getDistributionSD({ type: "beta", alpha: 2, beta: 4 });
    expect(result).toBeCloseTo(Math.sqrt(8 / (36 * 7)), 4);
  });

  it("should calculate SD for uniform", () => {
    // SD = (max - min) / sqrt(12)
    const result = getDistributionSD({ type: "uniform", min: 0, max: 10 });
    expect(result).toBeCloseTo(10 / Math.sqrt(12), 4);
  });
});

describe("parseIntervention", () => {
  const sampleYAML: YAMLIntervention = {
    id: "test_intervention",
    name: "Test Intervention",
    description: "A test intervention for unit tests",
    category: "exercise",
    keywords: ["test", "example"],
    evidence: {
      quality: "high",
      primary_study_type: "meta-analysis",
      sources: [
        { citation: "Test et al 2024", year: 2024, sample_size: 10000, contribution: "Main effect" },
      ],
    },
    mechanisms: {
      blood_pressure: {
        effect: "Normal(-4, 2)",
        direction: "decrease",
        units: "mmHg",
        evidence: "strong",
        source: "Test 2024",
      },
    },
    mortality: {
      hazard_ratio: "LogNormal(-0.18, 0.08)",
      onset_delay: 0.5,
      ramp_up: 1,
      decay_rate: 0.1,
    },
    quality: {
      subjective_wellbeing: "Normal(0.02, 0.01)",
      dimension_effects: [
        { dimension: "mobility", change: "Normal(0.03, 0.02)" },
      ],
    },
    caveats: ["This is a test"],
    profile_adjustments: [
      { condition: "age > 65", adjustment: "Reduce effect by 20%" },
    ],
  };

  it("should parse basic intervention properties", () => {
    const result = parseIntervention(sampleYAML);
    expect(result.description).toBe("A test intervention for unit tests");
    expect(result.category).toBe("exercise");
    expect(result.evidenceQuality).toBe("high");
  });

  it("should parse mechanism effects", () => {
    const result = parseIntervention(sampleYAML);
    expect(result.mechanismEffects).toHaveLength(1);
    expect(result.mechanismEffects[0].mechanism).toBe("blood_pressure");
    expect(result.mechanismEffects[0].direction).toBe("decrease");
    expect(result.mechanismEffects[0].effectSize).toEqual({ type: "normal", mean: -4, sd: 2 });
  });

  it("should parse mortality effect", () => {
    const result = parseIntervention(sampleYAML);
    expect(result.mortality).not.toBeNull();
    expect(result.mortality?.hazardRatio).toEqual({ type: "lognormal", logMean: -0.18, logSd: 0.08 });
    expect(result.mortality?.onsetDelay).toBe(0.5);
    expect(result.mortality?.rampUpPeriod).toBe(1);
    expect(result.mortality?.decayRate).toBe(0.1);
  });

  it("should parse quality effect", () => {
    const result = parseIntervention(sampleYAML);
    expect(result.quality).not.toBeNull();
    expect(result.quality?.subjectiveWellbeing).toEqual({ type: "normal", mean: 0.02, sd: 0.01 });
    expect(result.quality?.directDimensionEffects).toHaveLength(1);
  });

  it("should parse key sources", () => {
    const result = parseIntervention(sampleYAML);
    expect(result.keySources).toHaveLength(1);
    expect(result.keySources[0].citation).toBe("Test et al 2024");
    expect(result.keySources[0].sampleSize).toBe(10000);
  });

  it("should parse caveats and profile adjustments", () => {
    const result = parseIntervention(sampleYAML);
    expect(result.caveats).toContain("This is a test");
    expect(result.profileAdjustments).toContain("Reduce effect by 20%");
  });
});

describe("parseConfounding", () => {
  it("should parse Beta prior from YAML", () => {
    const yaml: YAMLIntervention = {
      id: "test",
      name: "Test",
      category: "exercise",
      confounding: {
        prior: { type: "beta", alpha: 2.5, beta: 5.0 },
        rationale: "Test rationale",
        calibration_sources: ["Source 1", "Source 2"],
      },
    };

    const result = parseConfounding(yaml);
    expect(result).not.toBeNull();
    expect(result?.causalFraction.alpha).toBe(2.5);
    expect(result?.causalFraction.beta).toBe(5.0);
    expect(result?.rationale).toBe("Test rationale");
    expect(result?.calibrationSources).toHaveLength(2);
  });

  it("should parse shorthand Beta prior", () => {
    const yaml: YAMLIntervention = {
      id: "test",
      name: "Test",
      category: "diet",
      confounding: {
        prior: "Beta(1.5, 4.5)",
      },
    };

    const result = parseConfounding(yaml);
    expect(result?.causalFraction.alpha).toBe(1.5);
    expect(result?.causalFraction.beta).toBe(4.5);
  });

  it("should return null when no confounding config", () => {
    const yaml: YAMLIntervention = {
      id: "test",
      name: "Test",
      category: "medical",
    };

    expect(parseConfounding(yaml)).toBeNull();
  });

  it("should throw when prior is not Beta", () => {
    const yaml: YAMLIntervention = {
      id: "test",
      name: "Test",
      category: "exercise",
      confounding: {
        prior: "Normal(0.25, 0.1)",
      },
    };

    expect(() => parseConfounding(yaml)).toThrow("Beta");
  });
});
