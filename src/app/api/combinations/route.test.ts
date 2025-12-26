/**
 * Tests for /api/combinations endpoint
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "next/server";

// Mock the intervention-combinations module
vi.mock("@/lib/qaly/intervention-combinations", () => ({
  getCombinedProfileQaly: vi.fn(),
}));

import { POST } from "./route";
import * as combinations from "@/lib/qaly/intervention-combinations";

describe("/api/combinations", () => {
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
    return new NextRequest("http://localhost:3000/api/combinations", {
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
    const req = createRequest({
      selectedInterventions: ["walking_30min_daily"],
    });
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid profile");
  });

  it("returns 400 for invalid profile age", async () => {
    const req = createRequest({
      profile: { ...validProfile, age: -5 },
      selectedInterventions: ["walking_30min_daily"],
    });
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid profile");
  });

  it("returns 400 for invalid profile sex", async () => {
    const req = createRequest({
      profile: { ...validProfile, sex: "invalid" },
      selectedInterventions: ["walking_30min_daily"],
    });
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid profile");
  });

  it("returns 400 for invalid selectedInterventions (not array)", async () => {
    const req = createRequest({
      profile: validProfile,
      selectedInterventions: "walking_30min_daily",
    });
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid selectedInterventions");
  });

  it("returns 400 for invalid selectedInterventions (not strings)", async () => {
    const req = createRequest({
      profile: validProfile,
      selectedInterventions: [1, 2, 3],
    });
    const response = await POST(req);

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toContain("Invalid selectedInterventions");
  });

  it("returns 500 when getCombinedProfileQaly returns null", async () => {
    vi.mocked(combinations.getCombinedProfileQaly).mockResolvedValue(null);

    const req = createRequest({
      profile: validProfile,
      selectedInterventions: ["walking_30min_daily"],
    });
    const response = await POST(req);

    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toContain("Failed to calculate combined QALY");
  });

  it("returns 200 with valid combined QALY data", async () => {
    const mockResult = {
      totalQaly: 0.5,
      individualQalys: {
        walking_30min_daily: 0.3,
        sleep_8_hours: 0.25,
      },
      overlapAdjustments: {
        sleep_8_hours: 0.9,
      },
      diminishingReturnsFactor: 0.95,
      interventionIds: ["walking_30min_daily", "sleep_8_hours"],
    };

    vi.mocked(combinations.getCombinedProfileQaly).mockResolvedValue(mockResult);

    const req = createRequest({
      profile: validProfile,
      selectedInterventions: ["walking_30min_daily", "sleep_8_hours"],
    });
    const response = await POST(req);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.totalQaly).toBe(0.5);
    expect(data.individualQalys).toEqual(mockResult.individualQalys);
    expect(data.overlapAdjustments).toEqual(mockResult.overlapAdjustments);
    expect(data.diminishingReturnsFactor).toBe(0.95);
    expect(data.interventionIds).toEqual(mockResult.interventionIds);
  });

  it("calls getCombinedProfileQaly with correct parameters", async () => {
    const mockResult = {
      totalQaly: 0.3,
      individualQalys: { walking_30min_daily: 0.3 },
      overlapAdjustments: {},
      diminishingReturnsFactor: 1.0,
      interventionIds: ["walking_30min_daily"],
    };

    vi.mocked(combinations.getCombinedProfileQaly).mockResolvedValue(mockResult);

    const req = createRequest({
      profile: validProfile,
      selectedInterventions: ["walking_30min_daily"],
      options: {
        applyOverlap: false,
        applyDiminishingReturns: true,
      },
    });
    await POST(req);

    expect(combinations.getCombinedProfileQaly).toHaveBeenCalledWith(
      ["walking_30min_daily"],
      validProfile,
      {
        applyOverlap: false,
        applyDiminishingReturns: true,
      }
    );
  });

  it("handles empty interventions array", async () => {
    const mockResult = {
      totalQaly: 0,
      individualQalys: {},
      overlapAdjustments: {},
      diminishingReturnsFactor: 1.0,
      interventionIds: [],
    };

    vi.mocked(combinations.getCombinedProfileQaly).mockResolvedValue(mockResult);

    const req = createRequest({
      profile: validProfile,
      selectedInterventions: [],
    });
    const response = await POST(req);

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.totalQaly).toBe(0);
    expect(data.interventionIds).toEqual([]);
  });

  it("uses default values for optional profile fields", async () => {
    const mockResult = {
      totalQaly: 0.3,
      individualQalys: { walking_30min_daily: 0.3 },
      overlapAdjustments: {},
      diminishingReturnsFactor: 1.0,
      interventionIds: ["walking_30min_daily"],
    };

    vi.mocked(combinations.getCombinedProfileQaly).mockResolvedValue(mockResult);

    const minimalProfile = {
      age: 35,
      sex: "male",
      bmiCategory: "normal",
      smokingStatus: "never",
      hasDiabetes: false,
    };

    const req = createRequest({
      profile: minimalProfile,
      selectedInterventions: ["walking_30min_daily"],
    });
    await POST(req);

    expect(combinations.getCombinedProfileQaly).toHaveBeenCalledWith(
      ["walking_30min_daily"],
      {
        ...minimalProfile,
        hasHypertension: false,
        activityLevel: "light",
      },
      undefined
    );
  });
});
