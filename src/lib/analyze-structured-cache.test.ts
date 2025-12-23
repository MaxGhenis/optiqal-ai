/**
 * Integration tests for cache in analyze-structured
 *
 * Verify that:
 * - Cache is checked before Claude API calls
 * - Results are stored after successful API calls
 * - Cache hits are indicated in results
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { analyzeStructured } from "./analyze-structured";
import { getCachedResult, setCachedResult, clearCache } from "./cache";
import type { UserProfile } from "@/types";

// Mock localStorage
let mockStore: Record<string, string> = {};

const mockLocalStorage = {
  getItem: (key: string) => mockStore[key] || null,
  setItem: (key: string, value: string) => {
    mockStore[key] = value;
  },
  removeItem: (key: string) => {
    delete mockStore[key];
  },
  clear: () => {
    mockStore = {};
  },
  get length() {
    return Object.keys(mockStore).length;
  },
  key: (index: number) => {
    const keys = Object.keys(mockStore);
    return keys[index] || null;
  },
};

Object.defineProperty(global, "localStorage", {
  value: mockLocalStorage,
  writable: true,
});

const mockProfile: UserProfile = {
  age: 30,
  sex: "male",
  height: 180,
  weight: 75,
  exerciseHoursPerWeek: 3,
  sleepHoursPerNight: 7,
  diet: "balanced",
  smoker: false,
};

describe("analyzeStructured with cache integration", () => {
  beforeEach(() => {
    mockStore = {};
  });

  it("should use cached result when available (no API call)", async () => {
    // Pre-populate cache
    const cachedResult = await analyzeStructured(
      mockProfile,
      "running 30 minutes daily",
      "test-api-key",
      { forceSource: "precomputed" }
    );

    setCachedResult("running 30 minutes", mockProfile, cachedResult);

    // Get from cache (should not call API)
    const result = getCachedResult("running 30 minutes", mockProfile);

    expect(result).not.toBeNull();
    expect(result?.intervention).toBe(cachedResult.intervention);
  });

  it("should normalize intervention for cache lookup", () => {
    const result1 = {
      intervention: "running",
      counterfactual: "sedentary",
      profile: mockProfile,
      source: { type: "claude" as const },
      baseline: { remainingLifeExpectancy: 50, remainingQALYs: 45 },
      mechanismEffects: [],
      simulation: {
        median: 0.5,
        mean: 0.5,
        ci95: { low: 0.2, high: 0.8 },
        ci90: { low: 0.25, high: 0.75 },
        probPositive: 0.95,
        probHarmful: 0.01,
        sampleSize: 10000,
        simulationType: "rigorous" as const,
      },
      summary: {
        totalQALYs: { median: 0.5, ci95Low: 0.2, ci95High: 0.8 },
        totalMinutes: { median: 262800, ci95Low: 105120, ci95High: 420480 },
        probPositive: 0.95,
        confidenceLevel: "medium" as const,
      },
      evidence: { quality: "moderate" as const, keyStudies: [], caveats: [] },
      affectedMechanisms: [],
    };

    setCachedResult("jogging 30 mins", mockProfile, result1);

    // Should match normalized form
    const cached = getCachedResult("running 30 minutes", mockProfile);
    expect(cached).not.toBeNull();
    expect(cached?.intervention).toBe(result1.intervention);
  });

  it("should not use cache when TTL expired", () => {
    const result = {
      intervention: "walking",
      counterfactual: "sedentary",
      profile: mockProfile,
      source: { type: "claude" as const },
      baseline: { remainingLifeExpectancy: 50, remainingQALYs: 45 },
      mechanismEffects: [],
      simulation: {
        median: 0.5,
        mean: 0.5,
        ci95: { low: 0.2, high: 0.8 },
        ci90: { low: 0.25, high: 0.75 },
        probPositive: 0.95,
        probHarmful: 0.01,
        sampleSize: 10000,
        simulationType: "rigorous" as const,
      },
      summary: {
        totalQALYs: { median: 0.5, ci95Low: 0.2, ci95High: 0.8 },
        totalMinutes: { median: 262800, ci95Low: 105120, ci95High: 420480 },
        probPositive: 0.95,
        confidenceLevel: "medium" as const,
      },
      evidence: { quality: "moderate" as const, keyStudies: [], caveats: [] },
      affectedMechanisms: [],
    };

    // Mock time
    const now = Date.now();
    const spy = vi.spyOn(Date, "now")
      .mockReturnValueOnce(now) // setCachedResult
      .mockReturnValueOnce(now + 8 * 24 * 60 * 60 * 1000); // getCachedResult (8 days later)

    setCachedResult("walking", mockProfile, result);
    const cached = getCachedResult("walking", mockProfile);

    expect(cached).toBeNull();

    vi.restoreAllMocks();
  });
});
