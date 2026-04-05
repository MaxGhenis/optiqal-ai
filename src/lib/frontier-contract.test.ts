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
});
