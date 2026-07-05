import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { BaselineWorkbench } from "@/components/predict/baseline-workbench";
import type { BaselineResponse } from "@/lib/baseline-types";

function makeResponse(
  pointEstimate: Partial<BaselineResponse["point_estimate"]> = {}
): BaselineResponse {
  return {
    meta: {
      model: "baseline_v1",
      qaly_discount_rate: 0,
      explicit_inputs_only: true,
      profile: {
        age: 39,
        sex: "male",
        bmi_category: "normal",
        smoking_status: "never",
        has_diabetes: false,
        has_hypertension: false,
        activity_level: "active",
      },
    },
    point_estimate: {
      remaining_life_expectancy: 41.2,
      expected_death_age: 80.2,
      remaining_qalys: 35.1,
      current_quality_weight: 0.96,
      ...pointEstimate,
    },
    risk: {
      lifestyle_multiplier: 0.92,
      condition_multiplier: 1,
      sleep_multiplier: 1.03,
      raw_multiplier: 0.95,
      calibration_factor: 1.01,
      calibrated_multiplier: 0.96,
    },
    survival_curve: [
      { age: 39, survival_probability: 1, quality_weight: 0.96, expected_qaly: 0.96 },
    ],
    sleep_estimate: null,
  };
}

function mockFetchOnce(response: BaselineResponse) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => response,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("BaselineWorkbench", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the medical disclaimer", async () => {
    mockFetchOnce(makeResponse());
    render(<BaselineWorkbench />);
    // Auto-runs after hydration; wait for results.
    await screen.findByText(/remaining life expectancy/i);
    expect(
      screen.getAllByText(/statistical estimates, not medical advice/i).length
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/consult a healthcare professional before acting/i).length
    ).toBeGreaterThan(0);
  });

  it("renders confidence intervals next to life expectancy and QALYs", async () => {
    mockFetchOnce(
      makeResponse({
        remaining_life_expectancy: 41.2,
        remaining_life_expectancy_ci: [36.4, 45.9],
        remaining_qalys: 35.1,
        remaining_qalys_ci: [30.2, 39.7],
      })
    );
    render(<BaselineWorkbench />);
    await screen.findByText(/remaining life expectancy/i);

    // Range bounds rounded to whole years to reduce false precision.
    expect(screen.getByText(/range 36\s*[–-]\s*46/i)).toBeInTheDocument();
    expect(screen.getByText(/range 30\s*[–-]\s*40/i)).toBeInTheDocument();
  });

  it("omits ranges when the response has no confidence intervals", async () => {
    mockFetchOnce(makeResponse());
    render(<BaselineWorkbench />);
    await screen.findByText(/remaining life expectancy/i);
    expect(screen.queryByText(/range/i)).toBeNull();
  });
});
