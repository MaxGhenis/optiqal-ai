/**
 * Tests for /api/portfolio endpoint
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

// Mock the modules
vi.mock("@/lib/qaly/intervention-combinations", () => ({
  findOptimalPortfolio: vi.fn(),
}));

vi.mock("@/lib/qaly/precomputed-profiles", () => ({
  getProfileQALY: vi.fn(),
}));

import { POST } from "./route";
import * as combinations from "@/lib/qaly/intervention-combinations";
import * as profiles from "@/lib/qaly/precomputed-profiles";

describe("/api/portfolio", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const validProfile = {
    age: 35,
    sex: "male",
    bmiCategory: "normal",
    smokingStatus: "never",
    hasDiabetes: false,
    hasHypertension: false,
    activityLevel: "light",
  };

  const createRequest = (body: unknown) => {
    return new NextRequest("http://localhost:3000/api/portfolio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  };

  it("returns 400 for invalid request body", async () => {
    const req = createRequest(null);
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid request body");
  });

  it("returns 400 for missing profile", async () => {
    const req = createRequest({});
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid profile");
  });

  it("returns 400 for invalid profile", async () => {
    const req = createRequest({
      profile: { age: -5, sex: "invalid" },
    });
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid profile");
  });

  it("returns 400 when all interventions are excluded", async () => {
    const req = createRequest({
      profile: validProfile,
      excludedInterventions: [
        "walking_30min_daily",
        "daily_exercise_moderate",
        "strength_training",
        "mediterranean_diet",
        "fish_oil_supplement",
        "quit_smoking",
        "moderate_alcohol",
        "meditation_daily",
        "sleep_8_hours",
        "daily_sunscreen",
      ],
    });
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("No interventions available");
  });

  it("returns 500 when no QALY data is available", async () => {
    // Mock getProfileQALY to return null for all interventions
    vi.mocked(profiles.getProfileQALY).mockResolvedValue(null);

    const req = createRequest({
      profile: validProfile,
    });
    const response = await POST(req);

    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toContain("No precomputed QALY data available");
  });

  it("returns 200 with optimal portfolio", async () => {
    // Mock getProfileQALY to return data for interventions
    vi.mocked(profiles.getProfileQALY).mockImplementation(async (id) => {
      const qalyValues: Record<string, number> = {
        walking_30min_daily: 0.3,
        sleep_8_hours: 0.25,
        mediterranean_diet: 0.2,
      };

      if (id in qalyValues) {
        return {
          qalyMedian: qalyValues[id],
          qalyMean: qalyValues[id],
          qalyCi95Low: qalyValues[id] * 0.8,
          qalyCi95High: qalyValues[id] * 1.2,
          cvdContribution: qalyValues[id] * 0.5,
          cancerContribution: qalyValues[id] * 0.3,
          otherContribution: qalyValues[id] * 0.2,
          lifeYearsGained: qalyValues[id] * 2,
          causalFractionMean: 0.8,
          baselineMortalityMultiplier: 1.0,
          interventionEffectModifier: 1.0,
        };
      }
      return null;
    });

    // Mock findOptimalPortfolio
    const mockPortfolio = [
      {
        interventionIds: ["walking_30min_daily"],
        totalQaly: 0.3,
        marginalQaly: 0.3,
        addedIntervention: "walking_30min_daily",
      },
      {
        interventionIds: ["walking_30min_daily", "sleep_8_hours"],
        totalQaly: 0.52,
        marginalQaly: 0.22,
        addedIntervention: "sleep_8_hours",
      },
    ];
    vi.mocked(combinations.findOptimalPortfolio).mockReturnValue(mockPortfolio);

    const req = createRequest({
      profile: validProfile,
    });
    const response = await POST(req);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.portfolio).toEqual(mockPortfolio);
    expect(data.availableInterventions).toContain("walking_30min_daily");
    expect(data.availableInterventions).toContain("sleep_8_hours");
    expect(data.availableInterventions).toContain("mediterranean_diet");
  });

  it("respects excluded interventions", async () => {
    vi.mocked(profiles.getProfileQALY).mockImplementation(async (id) => {
      const qalyValues: Record<string, number> = {
        sleep_8_hours: 0.25,
        mediterranean_diet: 0.2,
      };

      if (id in qalyValues) {
        return {
          qalyMedian: qalyValues[id],
          qalyMean: qalyValues[id],
          qalyCi95Low: qalyValues[id] * 0.8,
          qalyCi95High: qalyValues[id] * 1.2,
          cvdContribution: qalyValues[id] * 0.5,
          cancerContribution: qalyValues[id] * 0.3,
          otherContribution: qalyValues[id] * 0.2,
          lifeYearsGained: qalyValues[id] * 2,
          causalFractionMean: 0.8,
          baselineMortalityMultiplier: 1.0,
          interventionEffectModifier: 1.0,
        };
      }
      return null;
    });

    vi.mocked(combinations.findOptimalPortfolio).mockReturnValue([
      {
        interventionIds: ["sleep_8_hours"],
        totalQaly: 0.25,
        marginalQaly: 0.25,
        addedIntervention: "sleep_8_hours",
      },
    ]);

    const req = createRequest({
      profile: validProfile,
      excludedInterventions: ["walking_30min_daily"],
    });
    const response = await POST(req);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.availableInterventions).not.toContain("walking_30min_daily");
    expect(data.availableInterventions).toContain("sleep_8_hours");
  });

  it("respects maxInterventions parameter", async () => {
    vi.mocked(profiles.getProfileQALY).mockImplementation(async (id) => {
      return {
        qalyMedian: 0.1,
        qalyMean: 0.1,
        qalyCi95Low: 0.08,
        qalyCi95High: 0.12,
        cvdContribution: 0.05,
        cancerContribution: 0.03,
        otherContribution: 0.02,
        lifeYearsGained: 0.2,
        causalFractionMean: 0.8,
        baselineMortalityMultiplier: 1.0,
        interventionEffectModifier: 1.0,
      };
    });

    vi.mocked(combinations.findOptimalPortfolio).mockReturnValue([]);

    const req = createRequest({
      profile: validProfile,
      maxInterventions: 3,
    });
    await POST(req);

    expect(combinations.findOptimalPortfolio).toHaveBeenCalledWith(
      expect.any(Object),
      3
    );
  });

  it("caps maxInterventions at 10", async () => {
    vi.mocked(profiles.getProfileQALY).mockImplementation(async (id) => {
      return {
        qalyMedian: 0.1,
        qalyMean: 0.1,
        qalyCi95Low: 0.08,
        qalyCi95High: 0.12,
        cvdContribution: 0.05,
        cancerContribution: 0.03,
        otherContribution: 0.02,
        lifeYearsGained: 0.2,
        causalFractionMean: 0.8,
        baselineMortalityMultiplier: 1.0,
        interventionEffectModifier: 1.0,
      };
    });

    vi.mocked(combinations.findOptimalPortfolio).mockReturnValue([]);

    const req = createRequest({
      profile: validProfile,
      maxInterventions: 100,
    });
    await POST(req);

    expect(combinations.findOptimalPortfolio).toHaveBeenCalledWith(
      expect.any(Object),
      10
    );
  });

  it("uses default maxInterventions of 5", async () => {
    vi.mocked(profiles.getProfileQALY).mockImplementation(async (id) => {
      return {
        qalyMedian: 0.1,
        qalyMean: 0.1,
        qalyCi95Low: 0.08,
        qalyCi95High: 0.12,
        cvdContribution: 0.05,
        cancerContribution: 0.03,
        otherContribution: 0.02,
        lifeYearsGained: 0.2,
        causalFractionMean: 0.8,
        baselineMortalityMultiplier: 1.0,
        interventionEffectModifier: 1.0,
      };
    });

    vi.mocked(combinations.findOptimalPortfolio).mockReturnValue([]);

    const req = createRequest({
      profile: validProfile,
    });
    await POST(req);

    expect(combinations.findOptimalPortfolio).toHaveBeenCalledWith(
      expect.any(Object),
      5
    );
  });

  it("uses default values for optional profile fields", async () => {
    vi.mocked(profiles.getProfileQALY).mockResolvedValue({
      qalyMedian: 0.1,
      qalyMean: 0.1,
      qalyCi95Low: 0.08,
      qalyCi95High: 0.12,
      cvdContribution: 0.05,
      cancerContribution: 0.03,
      otherContribution: 0.02,
      lifeYearsGained: 0.2,
      causalFractionMean: 0.8,
      baselineMortalityMultiplier: 1.0,
      interventionEffectModifier: 1.0,
    });

    vi.mocked(combinations.findOptimalPortfolio).mockReturnValue([]);

    const minimalProfile = {
      age: 35,
      sex: "male",
      bmiCategory: "normal",
      smokingStatus: "never",
      hasDiabetes: false,
    };

    const req = createRequest({
      profile: minimalProfile,
    });
    await POST(req);

    // Verify that getProfileQALY was called with profile including defaults
    expect(profiles.getProfileQALY).toHaveBeenCalledWith(
      expect.any(String),
      {
        ...minimalProfile,
        hasHypertension: false,
        activityLevel: "light",
      }
    );
  });
});
