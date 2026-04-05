export type FrontierActivityLevel = "sedentary" | "light" | "moderate" | "active";

export interface FrontierProfileInput {
  age: number;
  sex: "male" | "female" | "other";
  weight_kg: number;
  height_cm: number;
  smoker: boolean;
  has_diabetes: boolean;
  has_hypertension: boolean;
  activity_level: FrontierActivityLevel;
  sleep_hours_per_night?: number | null;
}

export interface FrontierSleepInput {
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

export interface FrontierRequest {
  profile: FrontierProfileInput;
  sleep_metrics?: FrontierSleepInput | null;
  n_simulations?: number;
}

export type FrontierAccessTier =
  | "behavioral"
  | "otc"
  | "generic_rx"
  | "brand_rx_prior_auth"
  | "dme_rx"
  | "specialist_device"
  | "cash_pay"
  | "multiple"
  | "none";

export interface FrontierAccessLeaf {
  tier: FrontierAccessTier;
  coverage_outlook: "na" | "likely" | "mixed" | "unlikely";
  friction: "low" | "medium" | "high";
  notes: string;
}

export interface FrontierAccessProfile extends FrontierAccessLeaf {
  item_accesses?: FrontierAccessLeaf[];
}

export interface FrontierItem {
  id: string;
  name: string;
  category: string;
  display_category: string;
  public_lane: "consumer_public" | "conditional_public" | "personal_only";
  annual_cost: number | null;
  total_cost: number;
  cost_per_qaly: number | null;
  total_qaly: number;
  days: number;
  p_benefit: number;
  p_harm: number;
  mort_qaly: number;
  harm_qaly: number;
  qol_qaly: number;
  sleep_qol_qaly: number;
  profile_effect_multiplier: number;
  airway_effect_multiplier: number;
  sleep_mortality_hr_multiplier: number;
  sleep_mortality_relief_fraction: number;
  interaction_tags: string[];
  benefit_tags: string[];
  notes: string;
  sources: string[];
  selected_in_frontier: boolean;
  pricing_status: "priced" | "free" | "unpriced";
  rankability_reason: string | null;
  access: FrontierAccessProfile;
}

export interface FrontierStep {
  step: number;
  added_intervention: string;
  added_name: string;
  marginal_qaly: number;
  marginal_days: number;
  marginal_cost_per_qaly: number | null;
  marginal_cost_value: number;
  marginal_interaction_qaly: number;
  total_qaly: number;
  total_days: number;
  interaction_penalty_qaly: number;
  interaction_penalty_days: number;
  total_cost_value: number;
  total_annual_cost: number;
  selected_interventions: string[];
}

export interface FrontierSleepEstimate {
  annual_qaly_loss: number;
  mortality_signal: number;
  component_losses: Record<string, number>;
  component_burdens: Record<string, number>;
  airway: {
    upper_airway_probability: number;
    nasal_inflammation_probability: number;
    mucus_probability: number;
    response_signal: number;
  } | null;
}

export interface FrontierDecisionStateSummary {
  item_ids: string[];
  base_qaly: number;
  base_days: number;
  interaction_penalty_qaly: number;
  adjusted_qaly: number;
  adjusted_days: number;
  total_annual_cost: number;
}

export interface FrontierDecisionOptionItem {
  id: string;
  name: string;
  days: number;
  annual_cost: number | null;
  cost_per_qaly: number | null;
  p_benefit: number;
  p_harm: number;
  access: FrontierAccessProfile;
}

export interface FrontierDecisionOption {
  id: string;
  label: string;
  added_item_ids: string[];
  added_items: FrontierDecisionOptionItem[];
  marginal_qaly: number;
  marginal_days: number;
  marginal_annual_cost: number;
  marginal_cost_value: number;
  marginal_cost_per_qaly: number | null;
  stack: FrontierDecisionStateSummary;
  access: FrontierAccessProfile;
}

export interface FrontierChoiceState {
  id: string;
  kind: "choice";
  label: string;
  description: string;
  baseline: FrontierDecisionStateSummary;
  best_biology_option_id: string | null;
  best_access_option_id: string | null;
  options: FrontierDecisionOption[];
}

export interface FrontierFrontierStateStep {
  step: number;
  id: string;
  name: string;
  marginal_qaly: number;
  marginal_days: number;
  marginal_cost_per_qaly: number | null;
  marginal_interaction_days: number;
  cumulative_days: number;
  total_annual_cost: number;
}

export interface FrontierFrontierState {
  id: string;
  kind: "frontier";
  label: string;
  description: string;
  baseline: FrontierDecisionStateSummary;
  steps: FrontierFrontierStateStep[];
}

export type FrontierDecisionState = FrontierChoiceState | FrontierFrontierState;

export interface FrontierDecisionSequenceStep {
  step: number;
  id: string;
  label: string;
  state_id?: string;
  preferred_state_id?: string;
  alternative_state_id?: string;
}

export interface FrontierResponse {
  meta: {
    selection_mode: string;
    analyzed_count: number;
    positive_count: number;
    qaly_discount_rate: number;
    cost_discount_rate: number;
    n_simulations: number;
    rankable_count: number;
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
  sleep_estimate: FrontierSleepEstimate | null;
  frontier: FrontierStep[];
  items: FrontierItem[];
  decision_states: FrontierDecisionState[];
  decision_sequence: FrontierDecisionSequenceStep[];
}
