export type BaselineActivityLevel = "sedentary" | "light" | "moderate" | "active";

export interface BaselineProfileInput {
  age: number;
  sex: "male" | "female" | "other";
  weight_kg: number;
  height_cm: number;
  smoker: boolean;
  has_diabetes: boolean;
  has_hypertension: boolean;
  activity_level: BaselineActivityLevel;
  sleep_hours_per_night?: number | null;
}

export interface BaselineSleepInput {
  duration_hours?: number | null;
  recovery_score?: number | null;
  sleep_quality_score?: number | null;
  waso_min?: number | null;
  routine_score?: number | null;
  social_jetlag_min?: number | null;
  latency_min?: number | null;
  breathing_score?: number | null;
  spo2?: number | null;
  snore_pct?: number | null;
  sleep_debt_min?: number | null;
  airway_response_signal?: number | null;
}

export interface BaselineRequest {
  profile: BaselineProfileInput;
  sleep_metrics?: BaselineSleepInput | null;
}

export interface BaselineResponse {
  meta: {
    model: string;
    qaly_discount_rate: number;
    explicit_inputs_only: boolean;
    profile: {
      age: number;
      sex: string;
      bmi_category: string;
      smoking_status: string;
      has_diabetes: boolean;
      has_hypertension: boolean;
      activity_level: string;
    };
  };
  point_estimate: {
    remaining_life_expectancy: number;
    expected_death_age: number;
    remaining_qalys: number;
    current_quality_weight: number;
    /** Optional 90% confidence interval for remaining life expectancy, as [low, high]. */
    remaining_life_expectancy_ci?: [number, number];
    /** Optional 90% confidence interval for remaining QALYs, as [low, high]. */
    remaining_qalys_ci?: [number, number];
  };
  risk: {
    lifestyle_multiplier: number;
    condition_multiplier: number;
    sleep_multiplier: number;
    raw_multiplier: number;
    calibration_factor: number;
    calibrated_multiplier: number;
  };
  survival_curve: Array<{
    age: number;
    survival_probability: number;
    quality_weight: number;
    expected_qaly: number;
  }>;
  sleep_estimate: {
    annual_qaly_loss: number;
    mortality_signal: number;
    baseline_hazard_multiplier: number;
    component_losses: Record<string, number>;
  } | null;
}
