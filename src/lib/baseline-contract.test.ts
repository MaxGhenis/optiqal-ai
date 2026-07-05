import { describe, expect, it } from "vitest";
import {
  parseBaselineRequest,
  parseBaselineResponse,
} from "@/lib/baseline-contract";

describe("baseline contract", () => {
  it("accepts valid request bodies", () => {
    const parsed = parseBaselineRequest({
      profile: {
        age: 39,
        sex: "male",
        weight_kg: 74.8,
        height_cm: 178,
        smoker: false,
        has_diabetes: false,
        has_hypertension: false,
        activity_level: "active",
        sleep_hours_per_night: 7,
      },
      sleep_metrics: {
        duration_hours: 6.9,
        breathing_score: 0.82,
      },
    });

    expect(parsed?.profile.activity_level).toBe("active");
    expect(parsed?.sleep_metrics?.breathing_score).toBe(0.82);
  });

  it("rejects malformed request bodies", () => {
    expect(
      parseBaselineRequest({
        profile: {
          age: "39",
        },
      })
    ).toBeNull();
  });

  it("accepts valid baseline responses", () => {
    const parsed = parseBaselineResponse({
      meta: {
        model: "baseline_v1",
        qaly_discount_rate: 0.03,
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
        {
          age: 39,
          survival_probability: 1,
          quality_weight: 0.96,
          expected_qaly: 0.96,
        },
      ],
      sleep_estimate: {
        annual_qaly_loss: 0.01,
        mortality_signal: 0.02,
        baseline_hazard_multiplier: 1.01,
        component_losses: {
          airway: 0.01,
        },
      },
    });

    expect(parsed?.point_estimate.remaining_qalys).toBe(35.1);
    expect(parsed?.sleep_estimate?.baseline_hazard_multiplier).toBe(1.01);
  });

  const validPointEstimate = {
    remaining_life_expectancy: 41.2,
    expected_death_age: 80.2,
    remaining_qalys: 35.1,
    current_quality_weight: 0.96,
  };

  const validBaselineBody = {
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
    risk: {
      lifestyle_multiplier: 0.92,
      condition_multiplier: 1,
      sleep_multiplier: 1.03,
      raw_multiplier: 0.95,
      calibration_factor: 1.01,
      calibrated_multiplier: 0.96,
    },
    survival_curve: [],
    sleep_estimate: null,
  };

  it("parses baseline confidence intervals when present", () => {
    const parsed = parseBaselineResponse({
      ...validBaselineBody,
      point_estimate: {
        ...validPointEstimate,
        remaining_life_expectancy_ci: [36.4, 45.9],
        remaining_qalys_ci: [30.2, 39.7],
      },
    });

    expect(parsed?.point_estimate.remaining_life_expectancy_ci).toEqual([36.4, 45.9]);
    expect(parsed?.point_estimate.remaining_qalys_ci).toEqual([30.2, 39.7]);
  });

  it("still parses baseline responses that omit confidence intervals", () => {
    const parsed = parseBaselineResponse({
      ...validBaselineBody,
      point_estimate: validPointEstimate,
    });

    expect(parsed).not.toBeNull();
    expect(parsed?.point_estimate.remaining_life_expectancy_ci).toBeUndefined();
    expect(parsed?.point_estimate.remaining_qalys_ci).toBeUndefined();
  });

  it("rejects baseline responses with a malformed confidence interval", () => {
    expect(
      parseBaselineResponse({
        ...validBaselineBody,
        point_estimate: {
          ...validPointEstimate,
          remaining_qalys_ci: [30.2, "bad"],
        },
      })
    ).toBeNull();
    expect(
      parseBaselineResponse({
        ...validBaselineBody,
        point_estimate: {
          ...validPointEstimate,
          remaining_life_expectancy_ci: [36.4],
        },
      })
    ).toBeNull();
  });

  it("rejects malformed baseline responses", () => {
    expect(
      parseBaselineResponse({
        meta: {
          model: "baseline_v1",
          qaly_discount_rate: 0.03,
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
        },
        risk: {
          lifestyle_multiplier: 0.92,
          condition_multiplier: 1,
          sleep_multiplier: 1.03,
          raw_multiplier: 0.95,
          calibration_factor: 1.01,
          calibrated_multiplier: 0.96,
        },
        survival_curve: [{ age: "bad" }],
        sleep_estimate: null,
      })
    ).toBeNull();
  });
});
