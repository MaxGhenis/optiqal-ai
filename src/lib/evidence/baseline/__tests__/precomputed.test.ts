/**
 * Tests for precomputed baselines
 *
 * Note: These tests verify the structure and logic.
 * Integration tests in a browser environment would verify fetch() works.
 */

import { describe, it, expect } from "vitest";
import {
  getPrecomputedLifeExpectancy,
  getPrecomputedRemainingQALYs,
  getPrecomputedCauseFractions,
  getPrecomputedQualityWeight,
  type PrecomputedBaselines,
} from "../precomputed";

// Mock baselines data for testing
const mockBaselines: PrecomputedBaselines = {
  metadata: {
    version: "1.0.0",
    source: "CDC National Vital Statistics Life Tables (2021)",
    discount_rate: 0.03,
    max_age: 100,
  },
  life_expectancy: {
    male: {
      "0": 76.4,
      "40": 38.9,
      "41": 38.0,
      "100": 1.2,
    },
    female: {
      "0": 81.8,
      "40": 43.3,
      "41": 42.4,
      "100": 1.3,
    },
  },
  remaining_qalys: {
    male: {
      "0": 27.1,
      "40": 19.0,
      "41": 18.8,
      "100": 0.5,
    },
    female: {
      "0": 27.7,
      "40": 20.1,
      "41": 19.9,
      "100": 0.6,
    },
  },
  cause_fractions: {
    "0": { cvd: 0.2, cancer: 0.25, other: 0.55 },
    "40": { cvd: 0.2, cancer: 0.25, other: 0.55 },
    "41": { cvd: 0.2, cancer: 0.25, other: 0.55 },
    "100": { cvd: 0.45, cancer: 0.12, other: 0.43 },
  },
  quality_weights: {
    "0": 0.92,
    "40": 0.89,
    "41": 0.88,
    "100": 0.5,
  },
};

describe("Precomputed Baselines", () => {
  describe("getPrecomputedLifeExpectancy", () => {
    it("should return life expectancy for valid male age", () => {
      const result = getPrecomputedLifeExpectancy(40, "male", mockBaselines);
      expect(result).toBe(38.9);
    });

    it("should return life expectancy for valid female age", () => {
      const result = getPrecomputedLifeExpectancy(40, "female", mockBaselines);
      expect(result).toBe(43.3);
    });

    it("should return average for 'other' sex", () => {
      const result = getPrecomputedLifeExpectancy(40, "other", mockBaselines);
      expect(result).toBe((38.9 + 43.3) / 2);
    });

    it("should return null for age out of range", () => {
      const result = getPrecomputedLifeExpectancy(101, "male", mockBaselines);
      expect(result).toBeNull();
    });

    it("should return null for negative age", () => {
      const result = getPrecomputedLifeExpectancy(-1, "male", mockBaselines);
      expect(result).toBeNull();
    });

    it("should round age to nearest integer", () => {
      const result = getPrecomputedLifeExpectancy(39.7, "male", mockBaselines);
      expect(result).toBe(38.9); // Rounds to 40
    });
  });

  describe("getPrecomputedRemainingQALYs", () => {
    it("should return QALYs for valid male age", () => {
      const result = getPrecomputedRemainingQALYs(40, "male", mockBaselines);
      expect(result).toBe(19.0);
    });

    it("should return QALYs for valid female age", () => {
      const result = getPrecomputedRemainingQALYs(40, "female", mockBaselines);
      expect(result).toBe(20.1);
    });

    it("should return average for 'other' sex", () => {
      const result = getPrecomputedRemainingQALYs(40, "other", mockBaselines);
      expect(result).toBe((19.0 + 20.1) / 2);
    });

    it("should return null for age out of range", () => {
      const result = getPrecomputedRemainingQALYs(101, "male", mockBaselines);
      expect(result).toBeNull();
    });
  });

  describe("getPrecomputedCauseFractions", () => {
    it("should return cause fractions for valid age", () => {
      const result = getPrecomputedCauseFractions(40, mockBaselines);
      expect(result).toEqual({
        cvd: 0.2,
        cancer: 0.25,
        other: 0.55,
      });
    });

    it("should return null for age out of range", () => {
      const result = getPrecomputedCauseFractions(101, mockBaselines);
      expect(result).toBeNull();
    });

    it("should round age to nearest integer", () => {
      const result = getPrecomputedCauseFractions(40.4, mockBaselines);
      expect(result).toEqual({
        cvd: 0.2,
        cancer: 0.25,
        other: 0.55,
      });
    });
  });

  describe("getPrecomputedQualityWeight", () => {
    it("should return quality weight for valid age", () => {
      const result = getPrecomputedQualityWeight(40, mockBaselines);
      expect(result).toBe(0.89);
    });

    it("should return null for age out of range", () => {
      const result = getPrecomputedQualityWeight(101, mockBaselines);
      expect(result).toBeNull();
    });

    it("should round age to nearest integer", () => {
      const result = getPrecomputedQualityWeight(39.6, mockBaselines);
      expect(result).toBe(0.89); // Rounds to 40
    });
  });

  describe("Data structure validation", () => {
    it("should have correct metadata structure", () => {
      expect(mockBaselines.metadata).toHaveProperty("version");
      expect(mockBaselines.metadata).toHaveProperty("source");
      expect(mockBaselines.metadata).toHaveProperty("discount_rate");
      expect(mockBaselines.metadata).toHaveProperty("max_age");
      expect(mockBaselines.metadata.discount_rate).toBe(0.03);
    });

    it("should have male and female life expectancy data", () => {
      expect(mockBaselines.life_expectancy).toHaveProperty("male");
      expect(mockBaselines.life_expectancy).toHaveProperty("female");
    });

    it("should have male and female QALY data", () => {
      expect(mockBaselines.remaining_qalys).toHaveProperty("male");
      expect(mockBaselines.remaining_qalys).toHaveProperty("female");
    });

    it("should have cause fractions with all three categories", () => {
      const fractions = mockBaselines.cause_fractions["40"];
      expect(fractions).toHaveProperty("cvd");
      expect(fractions).toHaveProperty("cancer");
      expect(fractions).toHaveProperty("other");
    });

    it("cause fractions should sum to approximately 1", () => {
      const fractions = mockBaselines.cause_fractions["40"];
      const sum = fractions.cvd + fractions.cancer + fractions.other;
      expect(sum).toBeCloseTo(1.0, 2);
    });
  });

  describe("Edge cases", () => {
    it("should handle age 0 correctly", () => {
      const lifeExp = getPrecomputedLifeExpectancy(0, "male", mockBaselines);
      const qalys = getPrecomputedRemainingQALYs(0, "male", mockBaselines);
      expect(lifeExp).toBe(76.4);
      expect(qalys).toBe(27.1);
    });

    it("should handle age 100 correctly", () => {
      const lifeExp = getPrecomputedLifeExpectancy(100, "male", mockBaselines);
      const qalys = getPrecomputedRemainingQALYs(100, "male", mockBaselines);
      expect(lifeExp).toBe(1.2);
      expect(qalys).toBe(0.5);
    });

    it("should handle float ages by rounding", () => {
      const result1 = getPrecomputedLifeExpectancy(40.4, "male", mockBaselines);
      const result2 = getPrecomputedLifeExpectancy(40.6, "male", mockBaselines);
      expect(result1).toBe(38.9); // Rounds to 40
      expect(result2).toBe(38.0); // Rounds to 41
    });
  });

  describe("Sex parameter handling", () => {
    it("should handle 'male' correctly", () => {
      const result = getPrecomputedLifeExpectancy(0, "male", mockBaselines);
      expect(result).toBe(76.4);
    });

    it("should handle 'female' correctly", () => {
      const result = getPrecomputedLifeExpectancy(0, "female", mockBaselines);
      expect(result).toBe(81.8);
    });

    it("should handle 'other' by averaging male and female", () => {
      const result = getPrecomputedLifeExpectancy(0, "other", mockBaselines);
      expect(result).toBe((76.4 + 81.8) / 2);
    });
  });
});
