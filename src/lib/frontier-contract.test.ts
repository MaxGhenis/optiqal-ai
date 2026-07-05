import { describe, expect, it } from "vitest";
import {
  parseFrontierRequest,
  parseFrontierResponse,
} from "@/lib/frontier-contract";

describe("frontier contract", () => {
  it("accepts valid request bodies with optional sleep metrics", () => {
    const parsed = parseFrontierRequest({
      profile: {
        age: 39,
        sex: "male",
        weight_kg: 74.8,
        height_cm: 178,
        smoker: false,
        has_diabetes: false,
        has_hypertension: false,
        activity_level: "active",
      },
      sleep_metrics: {
        duration_hours: 6.8,
        spo2: 95.1,
      },
      n_simulations: 5000,
    });

    expect(parsed).toEqual({
      profile: {
        age: 39,
        sex: "male",
        weight_kg: 74.8,
        height_cm: 178,
        smoker: false,
        has_diabetes: false,
        has_hypertension: false,
        activity_level: "active",
      },
      sleep_metrics: {
        duration_hours: 6.8,
        spo2: 95.1,
      },
      n_simulations: 5000,
    });
  });

  it("rejects malformed request bodies", () => {
    expect(
      parseFrontierRequest({
        profile: {
          age: 39,
          sex: "male",
          weight_kg: 74.8,
          height_cm: 178,
          smoker: false,
          has_diabetes: false,
          has_hypertension: false,
          activity_level: "active",
        },
        sleep_metrics: {
          spo2: "bad",
        },
      })
    ).toBeNull();
  });

  const validProfile = {
    age: 39,
    sex: "male" as const,
    weight_kg: 74.8,
    height_cm: 178,
    smoker: false,
    has_diabetes: false,
    has_hypertension: false,
    activity_level: "active" as const,
  };

  it("rejects out-of-range profile values (DoS / div-by-zero guard)", () => {
    // Hostile age drives an effectively unbounded life-table loop.
    expect(
      parseFrontierRequest({ profile: { ...validProfile, age: -1_000_000 } })
    ).toBeNull();
    expect(
      parseFrontierRequest({ profile: { ...validProfile, age: 500 } })
    ).toBeNull();
    // Zero height divides by zero in BMI.
    expect(
      parseFrontierRequest({ profile: { ...validProfile, height_cm: 0 } })
    ).toBeNull();
    expect(
      parseFrontierRequest({ profile: { ...validProfile, weight_kg: 0 } })
    ).toBeNull();
  });

  it("rejects an out-of-range n_simulations (CPU/memory guard)", () => {
    expect(
      parseFrontierRequest({
        profile: validProfile,
        n_simulations: 100_000_000,
      })
    ).toBeNull();
    expect(
      parseFrontierRequest({ profile: validProfile, n_simulations: 0 })
    ).toBeNull();
  });

  it("accepts branching response payloads", () => {
    const parsed = parseFrontierResponse({
      meta: {
        selection_mode: "ordered_by_marginal_cost_per_qaly",
        analyzed_count: 1,
        positive_count: 1,
        qaly_discount_rate: 0.03,
        cost_discount_rate: 0.03,
        n_simulations: 5000,
        rankable_count: 1,
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
      sleep_estimate: null,
      public_policy: {
        lanes: [
          {
            id: "conditional_public",
            label: "Conditional public recommendations",
            description: "Shown only when a matching condition fires.",
            item_ids: ["apap_nightly"],
            item_count: 1,
            condition_ids: ["airway_signal"],
          },
        ],
        conditions: [
          {
            id: "airway_signal",
            label: "Airway-heavy sleep signal",
            description: "Triggered by airway-weighted sleep inputs.",
            item_ids: ["apap_nightly"],
            item_count: 1,
            evaluation_kind: "sleep_any_threshold",
            score_threshold: null,
            thresholds: [
              {
                signal: "sleep_breathing_burden",
                label: "Breathing burden",
                threshold: 0.05,
              },
            ],
            score_rules: [],
          },
        ],
        items: [
          {
            id: "apap_nightly",
            name: "APAP nightly",
            lane: "conditional_public",
            condition: "airway_signal",
            display_category: "sleep",
            explicitly_excluded: false,
          },
        ],
      },
      frontier: [],
      items: [
        {
          id: "apap_nightly",
          name: "APAP nightly",
          category: "sleep",
          display_category: "sleep",
          public_lane: "conditional_public",
          annual_cost: 300,
          total_cost: 1000,
          cost_per_qaly: 95000,
          total_qaly: 0.04,
          days: 14.6,
          p_benefit: 1,
          p_harm: 0,
          mort_qaly: 0,
          harm_qaly: 0,
          qol_qaly: 0.04,
          sleep_qol_qaly: 0.04,
          profile_effect_multiplier: 1,
          airway_effect_multiplier: 1.2,
          sleep_mortality_hr_multiplier: 1,
          sleep_mortality_relief_fraction: 0.5,
          interaction_tags: ["sleep_airway"],
          benefit_tags: ["sleep"],
          notes: "Test note",
          sources: ["https://example.com"],
          selected_in_frontier: true,
          pricing_status: "priced",
          rankability_reason: null,
          access: {
            tier: "dme_rx",
            coverage_outlook: "likely",
            friction: "medium",
            notes: "DME order required",
          },
        },
      ],
      decision_states: [
        {
          id: "primary_osa_therapy_choice",
          kind: "choice",
          label: "Primary OSA therapy choice",
          description: "Choose primary therapy.",
          baseline: {
            item_ids: [],
            base_qaly: 0,
            base_days: 0,
            interaction_penalty_qaly: 0,
            adjusted_qaly: 0,
            adjusted_days: 0,
            total_annual_cost: 0,
          },
          best_biology_option_id: "apap",
          best_access_option_id: "apap",
          options: [
            {
              id: "apap",
              label: "Start APAP",
              added_item_ids: ["apap_nightly"],
              added_items: [
                {
                  id: "apap_nightly",
                  name: "APAP nightly",
                  days: 14.6,
                  annual_cost: 300,
                  cost_per_qaly: 95000,
                  p_benefit: 1,
                  p_harm: 0,
                  access: {
                    tier: "dme_rx",
                    coverage_outlook: "likely",
                    friction: "medium",
                    notes: "DME order required",
                  },
                },
              ],
              marginal_qaly: 0.04,
              marginal_days: 14.6,
              marginal_annual_cost: 300,
              marginal_cost_value: 1000,
              marginal_cost_per_qaly: 95000,
              stack: {
                item_ids: ["apap_nightly"],
                base_qaly: 0.04,
                base_days: 14.6,
                interaction_penalty_qaly: 0,
                adjusted_qaly: 0.04,
                adjusted_days: 14.6,
                total_annual_cost: 300,
              },
              access: {
                tier: "dme_rx",
                coverage_outlook: "likely",
                friction: "medium",
                notes: "DME order required",
              },
            },
          ],
        },
      ],
      decision_sequence: [
        {
          step: 1,
          id: "primary_osa_therapy_choice",
          label: "Choose therapy",
          state_id: "primary_osa_therapy_choice",
        },
        {
          step: 2,
          id: "rx_after_apap_if_needed",
          label: "Only compare insomnia Rx later",
          preferred_state_id: "rx_after_apap_if_needed",
          alternative_state_id: "rx_after_oral_appliance_if_needed",
        },
      ],
    });

    expect(parsed?.decision_sequence[1]).toEqual({
      step: 2,
      id: "rx_after_apap_if_needed",
      label: "Only compare insomnia Rx later",
      preferred_state_id: "rx_after_apap_if_needed",
      alternative_state_id: "rx_after_oral_appliance_if_needed",
    });
    expect(parsed?.public_policy.lanes[0]?.condition_ids).toEqual(["airway_signal"]);
    expect(parsed?.public_policy.conditions[0]).toMatchObject({
      evaluation_kind: "sleep_any_threshold",
      score_threshold: null,
      thresholds: [{ signal: "sleep_breathing_burden", threshold: 0.05 }],
      score_rules: [],
    });
  });

  it("parses frontier item confidence intervals when present", () => {
    const parsed = parseFrontierResponse({
      meta: {
        selection_mode: "ordered_by_marginal_cost_per_qaly",
        analyzed_count: 1,
        positive_count: 1,
        qaly_discount_rate: 0,
        cost_discount_rate: 0,
        n_simulations: 5000,
        rankable_count: 1,
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
      sleep_estimate: null,
      public_policy: { lanes: [], conditions: [], items: [] },
      frontier: [],
      items: [
        {
          id: "head_elevation",
          name: "Head elevation nightly",
          category: "sleep",
          display_category: "behavioral",
          public_lane: "consumer_public",
          annual_cost: 0,
          total_cost: 0,
          cost_per_qaly: null,
          total_qaly: 0.12,
          net_qaly_ci: [0.02, 0.21],
          net_days_ci: [7.3, 76.6],
          days: 43.8,
          p_benefit: 0.68,
          p_harm: 0.04,
          mort_qaly: 0.1,
          harm_qaly: 0,
          qol_qaly: 0.02,
          sleep_qol_qaly: 0.02,
          profile_effect_multiplier: 1,
          airway_effect_multiplier: 1,
          sleep_mortality_hr_multiplier: 1,
          sleep_mortality_relief_fraction: 0,
          interaction_tags: [],
          benefit_tags: ["sleep"],
          notes: "",
          sources: [],
          selected_in_frontier: true,
          pricing_status: "free",
          rankability_reason: null,
          access: {
            tier: "behavioral",
            coverage_outlook: "na",
            friction: "low",
            notes: "",
          },
        },
      ],
      decision_states: [],
      decision_sequence: [],
    });

    expect(parsed?.items[0]?.net_qaly_ci).toEqual([0.02, 0.21]);
    expect(parsed?.items[0]?.net_days_ci).toEqual([7.3, 76.6]);
  });

  it("still parses frontier items that omit confidence intervals", () => {
    const parsed = parseFrontierResponse({
      meta: {
        selection_mode: "ordered_by_marginal_cost_per_qaly",
        analyzed_count: 1,
        positive_count: 1,
        qaly_discount_rate: 0,
        cost_discount_rate: 0,
        n_simulations: 5000,
        rankable_count: 1,
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
      sleep_estimate: null,
      public_policy: { lanes: [], conditions: [], items: [] },
      frontier: [],
      items: [
        {
          id: "head_elevation",
          name: "Head elevation nightly",
          category: "sleep",
          display_category: "behavioral",
          public_lane: "consumer_public",
          annual_cost: 0,
          total_cost: 0,
          cost_per_qaly: null,
          total_qaly: 0.12,
          days: 43.8,
          p_benefit: 0.68,
          p_harm: 0.04,
          mort_qaly: 0.1,
          harm_qaly: 0,
          qol_qaly: 0.02,
          sleep_qol_qaly: 0.02,
          profile_effect_multiplier: 1,
          airway_effect_multiplier: 1,
          sleep_mortality_hr_multiplier: 1,
          sleep_mortality_relief_fraction: 0,
          interaction_tags: [],
          benefit_tags: ["sleep"],
          notes: "",
          sources: [],
          selected_in_frontier: true,
          pricing_status: "free",
          rankability_reason: null,
          access: {
            tier: "behavioral",
            coverage_outlook: "na",
            friction: "low",
            notes: "",
          },
        },
      ],
      decision_states: [],
      decision_sequence: [],
    });

    expect(parsed).not.toBeNull();
    expect(parsed?.items[0]?.net_qaly_ci).toBeUndefined();
    expect(parsed?.items[0]?.net_days_ci).toBeUndefined();
  });

  it("rejects frontier items whose confidence interval is malformed", () => {
    const base = {
      meta: {
        selection_mode: "ordered_by_marginal_cost_per_qaly",
        analyzed_count: 1,
        positive_count: 1,
        qaly_discount_rate: 0,
        cost_discount_rate: 0,
        n_simulations: 5000,
        rankable_count: 1,
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
      sleep_estimate: null,
      public_policy: { lanes: [], conditions: [], items: [] },
      frontier: [],
      decision_states: [],
      decision_sequence: [],
    };
    const item = {
      id: "head_elevation",
      name: "Head elevation nightly",
      category: "sleep",
      display_category: "behavioral",
      public_lane: "consumer_public",
      annual_cost: 0,
      total_cost: 0,
      cost_per_qaly: null,
      total_qaly: 0.12,
      days: 43.8,
      p_benefit: 0.68,
      p_harm: 0.04,
      mort_qaly: 0.1,
      harm_qaly: 0,
      qol_qaly: 0.02,
      sleep_qol_qaly: 0.02,
      profile_effect_multiplier: 1,
      airway_effect_multiplier: 1,
      sleep_mortality_hr_multiplier: 1,
      sleep_mortality_relief_fraction: 0,
      interaction_tags: [],
      benefit_tags: ["sleep"],
      notes: "",
      sources: [],
      selected_in_frontier: true,
      pricing_status: "free",
      rankability_reason: null,
      access: {
        tier: "behavioral",
        coverage_outlook: "na",
        friction: "low",
        notes: "",
      },
    };

    expect(
      parseFrontierResponse({
        ...base,
        items: [{ ...item, net_qaly_ci: [0.02] }],
      })
    ).toBeNull();
    expect(
      parseFrontierResponse({
        ...base,
        items: [{ ...item, net_days_ci: [7.3, "bad"] }],
      })
    ).toBeNull();
  });

  it("rejects malformed nested response fields", () => {
    expect(
      parseFrontierResponse({
        meta: {
          selection_mode: "ordered_by_marginal_cost_per_qaly",
          analyzed_count: 1,
          positive_count: 1,
          qaly_discount_rate: 0.03,
          cost_discount_rate: 0.03,
          n_simulations: 5000,
          rankable_count: 1,
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
        sleep_estimate: null,
        public_policy: {
          lanes: [],
          conditions: [],
          items: [],
        },
        frontier: [],
        items: [
          {
            id: "broken",
            name: "Broken item",
          },
        ],
        decision_states: [],
        decision_sequence: [],
      })
    ).toBeNull();
  });

  it("accepts extended public policy condition ids from the python model", () => {
    const parsed = parseFrontierResponse({
      meta: {
        selection_mode: "ordered_by_marginal_cost_per_qaly",
        analyzed_count: 0,
        positive_count: 0,
        qaly_discount_rate: 0.03,
        cost_discount_rate: 0.03,
        n_simulations: 5000,
        rankable_count: 0,
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
      sleep_estimate: null,
      public_policy: {
        lanes: [
          {
            id: "conditional_public",
            label: "Conditional public recommendations",
            description: "Shown only when a matching condition fires.",
            item_ids: ["humidifier_nightly", "apap_nightly"],
            item_count: 2,
            condition_ids: ["nasal_dryness_signal", "osa_therapy_signal"],
          },
        ],
        conditions: [
          {
            id: "nasal_dryness_signal",
            label: "Nasal dryness signal",
            description: "Triggered by dryness-heavy sleep inputs.",
            item_ids: ["humidifier_nightly"],
            item_count: 1,
            evaluation_kind: "sleep_any_threshold",
            score_threshold: null,
            thresholds: [
              {
                signal: "sleep_nasal_dryness_burden",
                label: "Nasal dryness burden",
                threshold: 0.05,
              },
            ],
            score_rules: [],
          },
          {
            id: "osa_therapy_signal",
            label: "OSA therapy signal",
            description: "Triggered by stronger airway-weighted sleep inputs.",
            item_ids: ["apap_nightly"],
            item_count: 1,
            evaluation_kind: "sleep_any_threshold",
            score_threshold: null,
            thresholds: [
              {
                signal: "sleep_breathing_burden",
                label: "Breathing burden",
                threshold: 0.12,
              },
            ],
            score_rules: [],
          },
        ],
        items: [
          {
            id: "humidifier_nightly",
            name: "Humidifier nightly",
            lane: "conditional_public",
            condition: "nasal_dryness_signal",
            display_category: "sleep",
            explicitly_excluded: false,
          },
          {
            id: "apap_nightly",
            name: "APAP nightly",
            lane: "conditional_public",
            condition: "osa_therapy_signal",
            display_category: "sleep",
            explicitly_excluded: false,
          },
        ],
      },
      frontier: [],
      items: [],
      decision_states: [],
      decision_sequence: [],
    });

    expect(parsed?.public_policy.conditions.map((condition) => condition.id)).toEqual([
      "nasal_dryness_signal",
      "osa_therapy_signal",
    ]);
    expect(parsed?.public_policy.items.map((item) => item.condition)).toEqual([
      "nasal_dryness_signal",
      "osa_therapy_signal",
    ]);
  });
});
