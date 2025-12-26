/**
 * Tests for result caching layer
 *
 * Purpose: Reduce API costs by caching Claude analysis results
 */

import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import {
  normalizeIntervention,
  getCacheKey,
  getCachedResult,
  setCachedResult,
  clearCache,
  getCacheStats,
  pruneCacheIfNeeded,
} from "./cache";
import type { StructuredAnalysisResult } from "./analyze-structured";
import type { UserProfile } from "@/types";

// Mock localStorage - needs to persist across tests but can be cleared
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

// Replace global localStorage with mock
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
  diet: "omnivore",
  smoker: false,
  existingConditions: [],
  hasDiabetes: false,
  hasHypertension: false,
  activityLevel: "moderate",
};

const mockResult: StructuredAnalysisResult = {
  intervention: "walking 30 minutes daily",
  counterfactual: "sedentary behavior",
  profile: mockProfile,
  source: { type: "claude" },
  baseline: { remainingLifeExpectancy: 50, remainingQALYs: 45 },
  mechanismEffects: [],
  simulation: {
    median: 0.5,
    mean: 0.51,
    ci95: { low: 0.2, high: 0.8 },
    ci50: { low: 0.35, high: 0.65 },
    probPositive: 0.95,
    probMoreThanOneYear: 0.1,
    percentiles: [
      { p: 5, value: 0.1 },
      { p: 50, value: 0.5 },
      { p: 95, value: 0.9 },
    ],
    breakdown: {
      mortalityQALYs: { median: 0.3, ci95: { low: 0.1, high: 0.5 } },
      qualityQALYs: { median: 0.15, ci95: { low: 0.05, high: 0.25 } },
      costQALYs: { median: 0.05, ci95: { low: 0.01, high: 0.1 } },
    },
    nSimulations: 10000,
    lifecycle: {
      pathwayContributions: {
        cvd: { median: 0.2, ci95: { low: 0.1, high: 0.3 } },
        cancer: { median: 0.1, ci95: { low: 0.05, high: 0.15 } },
        other: { median: 0.2, ci95: { low: 0.1, high: 0.3 } },
      },
      lifeYearsGained: { median: 0.6, ci95: { low: 0.2, high: 1.0 } },
      discountRate: 0.03,
      used: true,
    },
  },
  summary: {
    totalQALYs: { median: 0.5, ci95Low: 0.2, ci95High: 0.8 },
    totalMinutes: { median: 262800, ci95Low: 105120, ci95High: 420480 },
    probPositive: 0.95,
    confidenceLevel: "medium",
  },
  evidence: {
    quality: "moderate",
    keyStudies: [],
    caveats: [],
  },
  affectedMechanisms: [],
};

describe("normalizeIntervention", () => {
  it("should convert to lowercase", () => {
    expect(normalizeIntervention("Walking")).toBe("walking");
    expect(normalizeIntervention("RUNNING")).toBe("running");
  });

  it("should trim whitespace", () => {
    expect(normalizeIntervention("  walking  ")).toBe("walking");
    expect(normalizeIntervention("\trunning\n")).toBe("running");
  });

  it("should normalize common time units", () => {
    expect(normalizeIntervention("walk 30 min daily")).toBe("walk 30 minutes daily");
    expect(normalizeIntervention("walk 30 mins daily")).toBe("walk 30 minutes daily");
    expect(normalizeIntervention("exercise 1 hr daily")).toBe("exercise 1 hours daily");
    expect(normalizeIntervention("exercise 2 hrs daily")).toBe("exercise 2 hours daily");
  });

  it("should normalize number words", () => {
    expect(normalizeIntervention("one apple")).toBe("1 apple");
    expect(normalizeIntervention("two cups coffee")).toBe("2 cups coffee");
    expect(normalizeIntervention("three servings")).toBe("3 servings");
  });

  it("should normalize common synonyms", () => {
    expect(normalizeIntervention("jogging")).toBe("running");
    expect(normalizeIntervention("strolling")).toBe("walking");
    expect(normalizeIntervention("bicycling")).toBe("cycling");
  });

  it("should handle multiple normalizations", () => {
    expect(normalizeIntervention("  Jogging 30 mins daily  ")).toBe("running 30 minutes daily");
  });

  it("should collapse multiple spaces", () => {
    expect(normalizeIntervention("walk    30    minutes")).toBe("walk 30 minutes");
  });
});

describe("getCacheKey", () => {
  it("should generate key from normalized intervention and profile", () => {
    const key1 = getCacheKey("walking 30 min", mockProfile);
    const key2 = getCacheKey("walking 30 minutes", mockProfile);

    // Same normalized form should produce same key
    expect(key1).toBe(key2);
  });

  it("should generate different keys for different profiles", () => {
    const profile1 = { ...mockProfile, age: 30 };
    const profile2 = { ...mockProfile, age: 40 };

    const key1 = getCacheKey("walking", profile1);
    const key2 = getCacheKey("walking", profile2);

    expect(key1).not.toBe(key2);
  });

  it("should include profile hash in key", () => {
    const key = getCacheKey("walking", mockProfile);
    expect(key).toContain("walking");
  });
});

describe("setCachedResult and getCachedResult", () => {
  beforeEach(() => {
    mockStore = {};
  });

  it("should cache and retrieve result", () => {
    setCachedResult("walking", mockProfile, mockResult);
    const cached = getCachedResult("walking", mockProfile);

    expect(cached).not.toBeNull();
    expect(cached?.intervention).toBe(mockResult.intervention);
    expect(cached?.summary.totalQALYs.median).toBe(mockResult.summary.totalQALYs.median);
  });

  it("should return null for cache miss", () => {
    const cached = getCachedResult("swimming", mockProfile);
    expect(cached).toBeNull();
  });

  it("should use normalized form for matching", () => {
    setCachedResult("walking 30 min", mockProfile, mockResult);
    const cached = getCachedResult("walking 30 minutes", mockProfile);

    expect(cached).not.toBeNull();
    expect(cached?.intervention).toBe(mockResult.intervention);
  });

  it("should not match different profiles", () => {
    const profile1 = { ...mockProfile, age: 30 };
    const profile2 = { ...mockProfile, age: 40 };

    setCachedResult("walking", profile1, mockResult);
    const cached = getCachedResult("walking", profile2);

    expect(cached).toBeNull();
  });

  it("should return null for expired entries", () => {
    // Mock Date.now to simulate time passing
    const now = Date.now();
    vi.spyOn(Date, "now")
      .mockReturnValueOnce(now) // setCachedResult
      .mockReturnValueOnce(now + 8 * 24 * 60 * 60 * 1000); // getCachedResult (8 days later)

    setCachedResult("walking", mockProfile, mockResult);
    const cached = getCachedResult("walking", mockProfile);

    expect(cached).toBeNull();

    vi.restoreAllMocks();
  });

  it("should not expire entries within TTL", () => {
    const now = Date.now();
    vi.spyOn(Date, "now")
      .mockReturnValueOnce(now) // setCachedResult
      .mockReturnValueOnce(now + 6 * 24 * 60 * 60 * 1000); // getCachedResult (6 days later)

    setCachedResult("walking", mockProfile, mockResult);
    const cached = getCachedResult("walking", mockProfile);

    expect(cached).not.toBeNull();

    vi.restoreAllMocks();
  });
});

describe("clearCache", () => {
  it("should remove all cache entries", () => {
    setCachedResult("walking", mockProfile, mockResult);
    setCachedResult("running", mockProfile, mockResult);

    clearCache();

    expect(getCachedResult("walking", mockProfile)).toBeNull();
    expect(getCachedResult("running", mockProfile)).toBeNull();
  });
});

describe("getCacheStats", () => {
  beforeEach(() => {
    mockStore = {};
  });

  it("should return zero for empty cache", () => {
    const stats = getCacheStats();
    expect(stats.totalEntries).toBe(0);
    expect(stats.totalSize).toBe(0);
  });

  it("should count cache entries", () => {
    setCachedResult("walking", mockProfile, mockResult);
    setCachedResult("running", mockProfile, mockResult);

    const stats = getCacheStats();
    expect(stats.totalEntries).toBe(2);
    expect(stats.totalSize).toBeGreaterThan(0);
  });

  it("should calculate size in bytes", () => {
    setCachedResult("walking", mockProfile, mockResult);

    const stats = getCacheStats();
    // Should be a reasonable size (> 100 bytes for JSON)
    expect(stats.totalSize).toBeGreaterThan(100);
  });

  it("should show oldest entry timestamp", () => {
    const now = Date.now();
    vi.spyOn(Date, "now")
      .mockReturnValueOnce(now)
      .mockReturnValueOnce(now + 1000);

    setCachedResult("walking", mockProfile, mockResult);
    setCachedResult("running", mockProfile, mockResult);

    const stats = getCacheStats();
    expect(stats.oldestEntry).toBe(now);

    vi.restoreAllMocks();
  });
});

describe("pruneCacheIfNeeded", () => {
  beforeEach(() => {
    mockStore = {};
  });

  it("should not prune when under max entries", () => {
    for (let i = 0; i < 50; i++) {
      setCachedResult(`intervention${i}`, mockProfile, mockResult);
    }

    pruneCacheIfNeeded();

    const stats = getCacheStats();
    expect(stats.totalEntries).toBe(50);
  });

  it("should prune oldest entries when over max", () => {
    // Mock Date.now to create entries with different timestamps
    let timestamp = Date.now();
    const spy = vi.spyOn(Date, "now");

    // Create 101 entries (just over max of 100)
    // Note: setCachedResult calls pruneCacheIfNeeded internally
    for (let i = 0; i < 101; i++) {
      spy.mockReturnValue(timestamp);
      setCachedResult(`intervention${i}`, mockProfile, mockResult);
      timestamp += 1000; // Each entry 1 second apart
    }

    // After the loop, pruning has already happened
    const stats = getCacheStats();
    // Should have pruned to 80 entries
    expect(stats.totalEntries).toBe(80);

    // Oldest entries should be removed
    expect(getCachedResult("intervention0", mockProfile)).toBeNull();
    expect(getCachedResult("intervention1", mockProfile)).toBeNull();

    // Newest entries should remain
    expect(getCachedResult("intervention100", mockProfile)).not.toBeNull();
    expect(getCachedResult("intervention99", mockProfile)).not.toBeNull();

    vi.restoreAllMocks();
  });

  it("should prune to 80% of max entries", () => {
    const spy = vi.spyOn(Date, "now");
    let timestamp = Date.now();

    // Create 101 entries - setCachedResult will auto-prune after hitting 101
    for (let i = 0; i < 101; i++) {
      spy.mockReturnValue(timestamp + i * 1000);
      setCachedResult(`intervention${i}`, mockProfile, mockResult);
    }

    // Auto-pruning during setCachedResult should have reduced to 80
    const stats = getCacheStats();
    expect(stats.totalEntries).toBe(80); // 80% of 100

    vi.restoreAllMocks();
  });
});
