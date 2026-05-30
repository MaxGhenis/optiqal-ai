"""Tests for personalized ground-up protocol assumptions."""

import math
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

import optiqal.protocol_ground_up as protocol_ground_up
from optiqal.catalog import CATALOG
from optiqal.genetics import GeneticProfile
from optiqal.protocol_ground_up import (
    PROFILE,
    StackSpec,
    apply_joint_fall_pathway,
    build_glp1_phenotype_model,
    build_additional_specs,
    build_current_stack_drop_table,
    build_decision_rankings,
    build_protocol_optimizers,
    build_state_marginal_decision_table,
    build_specs,
    cost_per_qaly,
    current_stack_interaction_tags,
    discount_factor,
    estimate_item,
    evaluate_protocol_state,
    latent_protocol_item_draws,
    latent_protocol_item_score,
    load_baseline,
    load_protocol_items,
    matching_genetic_rule_rationales,
    modeled_total_cost,
    optimize_protocol_state,
    profile_adjusted_observed_hr,
    profile_payload,
    qaly_lineage_payload,
    reference_case_payload,
    resolve_stack_spec,
    simulate_structured_qaly,
)
from optiqal.profile import Profile
from optiqal.protocol_personalization import (
    apply_protocol_spec,
    build_protocol_specs,
    load_protocol_context,
    load_protocol_profile,
)


def test_protocol_profile_has_single_active_source_of_truth():
    assert PROFILE.activity_level == "active"
    assert load_protocol_profile() == PROFILE


def test_hiit_three_times_weekly_does_not_exceed_two_for_current_baseline():
    baseline = load_baseline()
    specs = build_additional_specs(baseline)

    hiit_2 = specs["hiit_2x_week"]
    hiit_3 = specs["hiit_3x_week"]

    assert hiit_3.qol_annual <= hiit_2.qol_annual
    assert hiit_3.high_qaly <= hiit_2.high_qaly


def test_joint_fall_pathway_is_age_gated():
    spec = StackSpec(
        item_id="joint_test",
        observed_hr=1.0,
        log_sd=0.05,
        conf_alpha=1.0,
        conf_beta=5.0,
        qol_annual=0.0008,
        qol_years=10,
        low_qaly=0.0,
        high_qaly=0.01,
        personalization="Joint test",
        rationale="Joint test",
        sources=(),
    )

    younger = apply_joint_fall_pathway(
        spec,
        age=30,
        activity_level="active",
        joint_multiplier=0.5,
    )
    older = apply_joint_fall_pathway(
        spec,
        age=70,
        activity_level="light",
        joint_multiplier=0.5,
    )

    assert younger == spec
    assert older.qol_annual > spec.qol_annual
    assert older.observed_hr < spec.observed_hr


def test_fractional_discount_factor_and_cost_per_qaly():
    expected = 1 + 1 / 1.03 + 0.5 / 1.03**2
    assert discount_factor(2.5) == pytest.approx(expected)
    assert modeled_total_cost(100.0, 2.5) == pytest.approx(100 * expected)
    assert cost_per_qaly(250.0, 0.05) == 5000.0
    assert cost_per_qaly(250.0, -0.01) is None


def test_reference_case_payload_uses_current_reference_discounting():
    payload = reference_case_payload()

    assert payload["base"]["health_discount_rate"] == pytest.approx(0.03)
    assert payload["base"]["reporting_standard"] == "CHEERS 2022"
    assert payload["current_protocol_model"]["health_discount_rate"] == pytest.approx(0.03)
    assert payload["current_protocol_model"]["cost_discount_rate"] == pytest.approx(0.03)
    assert payload["current_protocol_model"]["discounting_matches_reference_case"] is True
    assert payload["current_protocol_model"]["is_formal_reference_case"] is False
    assert (
        payload["current_protocol_model"]["reference_case_alignment"]
        == "reference_case_discounting_with_fallback_utility_lineage"
    )
    assert 0.03 in payload["discount_sensitivity_rates"]


def test_qaly_lineage_flags_hand_estimated_qol_overlay():
    resolved = resolve_stack_spec(
        StackSpec(
            item_id="test",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=5.0,
            qol_annual=0.001,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.02,
            personalization="test",
            rationale="test",
            sources=(),
        ),
    )

    lineage = qaly_lineage_payload(
        resolved=resolved,
        mortality_qaly=0.0,
        direct_harm_qaly=0.0,
        general_qol_qaly=0.01,
        sleep_qol_qaly=0.0,
    )

    assert lineage["overall_reference_case_status"] == "needs_utility_lineage"
    assert "general_qol_needs_preference_based_utility_source" in lineage["issues"]


def test_qaly_lineage_accepts_general_qol_reference_case_source():
    resolved = resolve_stack_spec(
        StackSpec(
            item_id="test",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=5.0,
            qol_annual=0.001,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.02,
            personalization="test",
            rationale="test",
            sources=(),
            general_qol_utility_weight_ids=(
                "erectile_dysfunction_tto_utility_gain_stolk_2000",
            ),
            general_qol_lineage_note="small modeled fraction of a TTO utility gain",
        ),
    )

    lineage = qaly_lineage_payload(
        resolved=resolved,
        mortality_qaly=0.0,
        direct_harm_qaly=0.0,
        general_qol_qaly=0.01,
        sleep_qol_qaly=0.0,
    )

    general = lineage["components"]["general_qol"]
    utility_lineage = general["utility_lineage"][
        "erectile_dysfunction_tto_utility_gain_stolk_2000"
    ]

    assert lineage["overall_reference_case_status"] == "reference_case_ready"
    assert lineage["issues"] == []
    assert general["reference_case_status"] == "reference_case"
    assert utility_lineage["overlay_fraction_of_utility_decrement"] == pytest.approx(
        0.001 / 0.11,
        abs=1e-6,
    )
    assert "TTO utility gain" in utility_lineage["lineage_note"]


def test_qaly_lineage_marks_general_qol_disability_weight_as_fallback():
    resolved = resolve_stack_spec(
        StackSpec(
            item_id="test",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=5.0,
            qol_annual=0.001,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.02,
            personalization="test",
            rationale="test",
            sources=(),
            general_qol_utility_weight_ids=(
                "anxiety_disorders_mild_disability_weight_europe_2015",
            ),
        ),
    )

    lineage = qaly_lineage_payload(
        resolved=resolved,
        mortality_qaly=0.0,
        direct_harm_qaly=0.0,
        general_qol_qaly=0.01,
        sleep_qol_qaly=0.0,
    )

    assert lineage["overall_reference_case_status"] == "fallback_utility_lineage"
    assert "general_qol_uses_fallback_disability_weights" in lineage["issues"]
    assert lineage["components"]["general_qol"]["reference_case_status"] == "fallback"


def test_qaly_lineage_marks_direct_harm_disability_weight_as_fallback():
    resolved = resolve_stack_spec(
        StackSpec(
            item_id="test",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=5.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.02,
            personalization="test",
            rationale="test",
            sources=(),
        ),
    )

    lineage = qaly_lineage_payload(
        resolved=resolved,
        mortality_qaly=0.0,
        direct_harm_qaly=-0.002,
        general_qol_qaly=0.0,
        sleep_qol_qaly=0.0,
        direct_harm_lineage={
            "daytime_sedation": {
                "id": "daytime_sedation",
                "annual_qaly_loss": {
                    "type": "normal",
                    "params": {"mean": 0.0012, "sd": 0.0005},
                },
                "utility_lineage": {
                    "motor_impairment_mild_disability_weight_europe_2015": {
                        "reference_case_status": "fallback",
                    },
                },
            },
        },
    )

    assert lineage["overall_reference_case_status"] == "fallback_utility_lineage"
    assert "direct_harm_uses_fallback_disability_weights" in lineage["issues"]
    assert lineage["components"]["direct_harm"]["reference_case_status"] == "fallback"


def test_qaly_lineage_accepts_sleep_disability_weight_fallback():
    resolved = resolve_stack_spec(
        StackSpec(
            item_id="test",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=5.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.02,
            personalization="test",
            rationale="test",
            sources=(),
        ),
    )

    lineage = qaly_lineage_payload(
        resolved=resolved,
        mortality_qaly=0.0,
        direct_harm_qaly=0.0,
        general_qol_qaly=0.0,
        sleep_qol_qaly=0.01,
        sleep_lineage={
            "breathing": {
                "utility_weight_id": "sleep_apnoea_disability_weight_europe_2015",
                "reference_case_status": "fallback",
            },
        },
    )

    assert lineage["overall_reference_case_status"] == "fallback_utility_lineage"
    assert "sleep_qol_uses_fallback_disability_weights" in lineage["issues"]
    assert lineage["components"]["sleep_qol"]["reference_case_status"] == "fallback"


def test_profile_adjusted_observed_hr_applies_log_multiplier():
    assert profile_adjusted_observed_hr(0.8, 0.5) == pytest.approx(
        math.exp(math.log(0.8) * 0.5),
    )
    assert profile_adjusted_observed_hr(0.8, 1.0) == 0.8
    with pytest.raises(ValueError):
        profile_adjusted_observed_hr(0.0, 1.0)


def test_structured_simulation_uses_mean_centered_hr_lognormal(monkeypatch):
    captured = {}

    def fake_simulate(intervention, *args, **kwargs):
        captured["hazard_ratio"] = intervention.mortality.hazard_ratio
        return SimpleNamespace(
            mean=0.0,
            expected_harm_qalys=0.0,
            expected_interaction_harm_qalys=0.0,
            prob_positive=0.5,
            prob_negative=0.5,
        ), [0.0]

    monkeypatch.setattr(
        protocol_ground_up,
        "simulate_qaly_profile_vectorized",
        fake_simulate,
    )

    simulate_structured_qaly(
        StackSpec(
            item_id="omega3_epa_2g",
            observed_hr=0.98,
            log_sd=0.09,
            conf_alpha=2.5,
            conf_beta=4.5,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=-0.002,
            high_qaly=0.02,
            personalization="test",
            rationale="test",
            sources=(),
        ),
        "omega3_epa_2g",
    )

    assert captured["hazard_ratio"].params == {"hr": 0.98, "log_sd": 0.09}


def test_profile_payload_redacts_genetic_profile_details():
    profile = replace(
        PROFILE,
        genetic_profile=GeneticProfile(
            phenotypes={"CYP2D6": "ultrarapid_metabolizer"},
            chip_version="23andMe v3",
        ),
    )

    payload = profile_payload(profile)

    assert payload["genetic_profile"] == {
        "available": True,
        "phenotype_count": 1,
        "actionable_finding_count": 0,
        "chip_version": "23andMe v3",
    }
    assert "phenotypes" not in payload["genetic_profile"]


def test_matching_genetic_rule_rationales_reports_fired_rules():
    profile = replace(
        PROFILE,
        genetic_profile=GeneticProfile(
            phenotypes={"CYP2D6": "ultrarapid_metabolizer"},
        ),
    )

    rationales = matching_genetic_rule_rationales(
        CATALOG["trazodone_50mg"],
        profile,
    )

    assert rationales == [
        "CYP2D6 UM clears trazodone too quickly; reduced benefit at standard dose.",
    ]


def test_estimate_item_applies_catalog_profile_effect_rules_to_hr():
    baseline = load_baseline()
    spec = StackSpec(
        item_id="statin_5mg",
        observed_hr=0.8,
        log_sd=0.05,
        conf_alpha=2.0,
        conf_beta=5.0,
        qol_annual=0.0,
        qol_years=1,
        low_qaly=-0.01,
        high_qaly=0.03,
        personalization="Profile-rule test",
        rationale="Profile-rule test",
        sources=(),
    )
    item = {
        "id": "statin_5mg",
        "name": "Statin test",
        "status": "considering",
        "category": "rx_candidate",
        "display_category": "rx",
        "annual_cost": 120,
    }

    estimate = estimate_item(item, spec, baseline)
    multiplier = CATALOG["statin_5mg"].profile_effect_multiplier(PROFILE)

    assert multiplier < 1.0
    assert estimate["assumptions"]["profile_effect_multiplier"] == pytest.approx(
        multiplier,
    )
    assert estimate["assumptions"]["effective_observed_hr"] == pytest.approx(
        profile_adjusted_observed_hr(0.8, multiplier),
    )


def test_glp1_model_keeps_lean_low_risk_profile_harm_dominated():
    baseline = load_baseline()
    model = build_glp1_phenotype_model(baseline, PROFILE)
    specs = build_additional_specs(baseline)
    item = {
        "id": "semaglutide",
        "name": "Semaglutide test",
        "status": "considering",
        "category": "rx_candidate",
        "display_category": "rx",
        "annual_cost": CATALOG["semaglutide"].annual_cost,
    }

    estimate = estimate_item(item, specs["semaglutide"], baseline)

    assert model["bmi_category"] == "normal"
    assert model["durable_weight_loss_fraction"] == 0.0
    assert model["observed_hr"] == pytest.approx(1.0)
    assert model["net_qol_annual"] < 0.0
    assert specs["semaglutide"].apply_profile_effect_rules is False
    assert estimate["mortality_qaly"] == pytest.approx(0.0, abs=1e-4)
    assert estimate["total_qaly"] < estimate["direct_harm_qaly"]
    assert estimate["assumptions"]["model_details"]["annual_off_label_penalty"] > 0.0


def test_glp1_model_upweights_obesity_metabolic_profile():
    baseline = load_baseline()
    baseline = {
        **baseline,
        "labs": {
            **baseline["labs"],
            "HbA1c": 5.8,
            "Glucose": 104,
        },
        "derived": {
            **baseline["derived"],
            "cardio_need": 0.6,
        },
    }
    context = replace(
        load_protocol_context(),
        profile=Profile(
            age=58,
            sex="male",
            bmi_category="obese",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=True,
            activity_level="light",
        ),
    )

    spec = build_additional_specs(baseline, context)["semaglutide"]
    model = spec.model_details

    assert model is not None
    assert model["durable_weight_loss_fraction"] > 0.07
    assert model["excess_bmi_reversal_fraction"] > 0.3
    assert spec.observed_hr < 1.0
    assert spec.qol_annual > 0.0
    assert spec.sleep_component_relief["breathing"] > 0.0


def test_glp1_model_can_be_positive_in_severe_obesity_diabetes_profile():
    baseline = load_baseline()
    baseline = {
        **baseline,
        "labs": {
            **baseline["labs"],
            "HbA1c": 7.1,
            "Glucose": 132,
        },
        "derived": {
            **baseline["derived"],
            "cardio_need": 0.7,
        },
    }
    context = replace(
        load_protocol_context(),
        profile=Profile(
            age=52,
            sex="female",
            bmi_category="severely_obese",
            smoking_status="never",
            has_diabetes=True,
            has_hypertension=True,
            activity_level="light",
        ),
    )
    item = {
        "id": "semaglutide",
        "name": "Semaglutide test",
        "status": "considering",
        "category": "rx_candidate",
        "display_category": "rx",
        "annual_cost": CATALOG["semaglutide"].annual_cost,
    }

    spec = build_additional_specs(baseline, context)["semaglutide"]
    estimate = estimate_item(item, spec, baseline, context)

    assert estimate["total_qaly"] > 0.0
    assert estimate["assumptions"]["effective_observed_hr"] < 1.0
    assert estimate["assumptions"]["model_details"]["diabetes_signal"] == 1.0


def test_protocol_items_include_decision_display_category():
    items = {item["id"]: item for item in load_protocol_items()}

    assert items["hiit_2x_week"]["display_category"] == "exercise"
    assert items["traditional_sauna_4x_week"]["display_category"] == "service"
    assert items["glycine_2g"]["display_category"] == "supplement"


def test_current_stack_interaction_tags_excludes_target_item():
    protocol_items = [
        {"id": "glycine_2g", "status": "testing"},
        {"id": "melatonin_300mcg", "status": "taking"},
        {"id": "daridorexant_25mg", "status": "considering"},
    ]

    assert current_stack_interaction_tags(protocol_items) == ("sedating", "sedating")
    assert current_stack_interaction_tags(
        protocol_items,
        exclude_item_id="glycine_2g",
    ) == ("sedating",)


def test_estimate_item_applies_active_stack_interaction_harms():
    baseline = load_baseline()
    spec = build_additional_specs(baseline)["ashwagandha_600"]
    item = {
        "id": "ashwagandha_600",
        "name": "Ashwagandha test",
        "status": "testing",
        "category": "supplement_bought",
        "display_category": "supplement",
        "annual_cost": 60,
    }

    alone = estimate_item(item, spec, baseline)
    stacked = estimate_item(
        item,
        spec,
        baseline,
        active_interaction_tags=("sedating",),
    )

    assert stacked["direct_harm_qaly"] < alone["direct_harm_qaly"]
    assert "sedation_stack" in stacked["qaly_lineage"]["components"]["direct_harm"][
        "utility_lineage"
    ]


def test_stack_interaction_harm_is_allocated_across_matching_tags():
    baseline = load_baseline()
    spec = build_additional_specs(baseline)["glycine_2g"]
    item = {
        "id": "glycine_2g",
        "name": "Glycine test",
        "status": "testing",
        "category": "supplement_bought",
        "display_category": "supplement",
        "annual_cost": 28,
    }

    one_other_sedative = estimate_item(
        item,
        spec,
        baseline,
        active_interaction_tags=("sedating",),
    )
    several_other_sedatives = estimate_item(
        item,
        spec,
        baseline,
        active_interaction_tags=("sedating", "sedating", "sedating", "sedating"),
    )

    assert one_other_sedative["direct_harm_qaly"] < 0
    assert several_other_sedatives["direct_harm_qaly"] < 0
    assert several_other_sedatives["direct_harm_qaly"] > one_other_sedative[
        "direct_harm_qaly"
    ]


def test_protocol_state_counts_shared_stack_effects_once():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    protocol_items = {
        item["id"]: item
        for item in load_protocol_items()
        if item["id"] in {"glycine_2g", "apigenin_50"}
    }
    estimates_by_id = {
        item_id: estimate_item(
            protocol_items[item_id],
            specs[item_id],
            baseline,
            context,
            include_draws=True,
        )
        for item_id in protocol_items
    }

    state = evaluate_protocol_state(
        ["glycine_2g", "apigenin_50"],
        estimates_by_id,
        specs,
        context,
    )
    additive = (
        estimates_by_id["glycine_2g"]["total_qaly"]
        + estimates_by_id["apigenin_50"]["total_qaly"]
    )

    assert state["additive_qaly"] == pytest.approx(additive, abs=0.0001)
    assert state["stack_interaction_qaly"] < 0
    assert state["total_qaly"] < additive


def test_protocol_state_value_is_order_and_duplicate_invariant():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    item_ids = ["glycine_2g", "apigenin_50", "ashwagandha_600"]
    loaded_items = {item["id"]: item for item in load_protocol_items()}
    estimates_by_id = {
        item_id: estimate_item(
            loaded_items[item_id],
            specs[item_id],
            baseline,
            context,
            include_draws=True,
        )
        for item_id in item_ids
    }

    state_a = evaluate_protocol_state(
        ["glycine_2g", "apigenin_50", "glycine_2g", "ashwagandha_600"],
        estimates_by_id,
        specs,
        context,
    )
    state_b = evaluate_protocol_state(
        ["ashwagandha_600", "apigenin_50", "glycine_2g"],
        estimates_by_id,
        specs,
        context,
    )

    assert state_a["n_items"] == 3
    assert set(state_a["item_ids"]) == set(item_ids)
    assert state_a["total_qaly"] == pytest.approx(state_b["total_qaly"], abs=0.0001)
    assert state_a["stack_interaction_qaly"] == pytest.approx(
        state_b["stack_interaction_qaly"],
        abs=0.0001,
    )
    assert state_a["modeled_total_cost"] == state_b["modeled_total_cost"]


def test_state_marginal_delta_matches_direct_value_difference():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    item_ids = ["glycine_2g", "apigenin_50"]
    loaded_items = {item["id"]: item for item in load_protocol_items()}
    estimates_by_id = {
        item_id: estimate_item(
            loaded_items[item_id],
            specs[item_id],
            baseline,
            context,
            include_draws=True,
        )
        for item_id in item_ids
    }
    glycine_state = evaluate_protocol_state(
        ["glycine_2g"],
        estimates_by_id,
        specs,
        context,
    )
    pair_state = evaluate_protocol_state(
        item_ids,
        estimates_by_id,
        specs,
        context,
    )
    add_delta = float(np.mean(pair_state["_draws"] - glycine_state["_draws"]))
    drop_delta = float(np.mean(glycine_state["_draws"] - pair_state["_draws"]))

    assert add_delta == pytest.approx(-drop_delta)

    add_rows = build_state_marginal_decision_table(
        [
            {"id": "glycine_2g", "status": "testing"},
            {"id": "apigenin_50", "status": "considering"},
        ],
        estimates_by_id,
        specs,
        context,
    )
    drop_rows = build_state_marginal_decision_table(
        [
            {"id": "glycine_2g", "status": "testing"},
            {"id": "apigenin_50", "status": "testing"},
        ],
        estimates_by_id,
        specs,
        context,
    )

    add_row = next(row for row in add_rows if row["id"] == "apigenin_50")
    drop_row = next(row for row in drop_rows if row["id"] == "apigenin_50")
    assert add_row["delta_qaly"] == round(add_delta, 4)
    assert drop_row["delta_qaly"] == round(drop_delta, 4)
    assert add_row["paired_state_correlation"] > 0
    assert add_row["delta_sd"] < add_row["independent_delta_sd"]


def test_latent_protocol_draws_preserve_item_marginal_distribution():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    item = next(
        item for item in load_protocol_items()
        if item["id"] == "glycine_2g"
    )
    estimate = estimate_item(
        item,
        specs["glycine_2g"],
        baseline,
        context,
        include_draws=True,
    )

    latent_draws = latent_protocol_item_draws("glycine_2g", estimate)

    assert np.mean(latent_draws) == pytest.approx(np.mean(estimate["_total_draws"]))
    assert np.std(latent_draws) == pytest.approx(np.std(estimate["_total_draws"]))
    assert np.sort(latent_draws) == pytest.approx(np.sort(estimate["_total_draws"]))


def test_latent_protocol_scores_correlate_related_items_more_than_unrelated():
    glycine_score = latent_protocol_item_score("glycine_2g")
    apigenin_score = latent_protocol_item_score("apigenin_50")
    vitamin_d_score = latent_protocol_item_score("vitamin_d_2000")

    related_corr = float(np.corrcoef(glycine_score, apigenin_score)[0, 1])
    unrelated_corr = float(np.corrcoef(glycine_score, vitamin_d_score)[0, 1])

    assert related_corr > 0.10
    assert related_corr > unrelated_corr + 0.06


def test_state_marginal_decisions_use_full_state_delta():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    protocol_items = [
        {"id": "glycine_2g", "status": "testing"},
        {"id": "apigenin_50", "status": "testing"},
    ]
    loaded_items = {item["id"]: item for item in load_protocol_items()}
    estimates_by_id = {
        item["id"]: estimate_item(
            loaded_items[item["id"]],
            specs[item["id"]],
            baseline,
            context,
            include_draws=True,
        )
        for item in protocol_items
    }

    rows = build_state_marginal_decision_table(
        protocol_items,
        estimates_by_id,
        specs,
        context,
    )
    glycine_drop = next(row for row in rows if row["id"] == "glycine_2g")

    assert glycine_drop["action"] == "drop"
    assert glycine_drop["state_interaction_delta_qaly"] > 0
    assert glycine_drop["drop_qaly"] == glycine_drop["delta_qaly"]


def test_protocol_optimizer_enforces_exclusive_cardio_group():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    item_ids = ["hiit_1x_week", "hiit_2x_week", "tempo_run_1x_week"]
    loaded_items = {item["id"]: item for item in load_protocol_items()}
    estimates_by_id = {
        item_id: estimate_item(
            loaded_items[item_id],
            specs[item_id],
            baseline,
            context,
            include_draws=True,
        )
        for item_id in item_ids
    }
    protocol_items = [
        {"id": item_id, "status": "watching"}
        for item_id in item_ids
    ]

    result = optimize_protocol_state(
        protocol_items,
        estimates_by_id,
        specs,
        context,
        objective="qaly",
    )
    selected = set(result["recommended_state"]["item_ids"])

    assert "hiit_2x_week" in selected
    assert len(selected & set(item_ids)) == 1
    assert result["delta_qaly"] > 0


def test_protocol_optimizer_can_swap_exclusive_current_item():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    item_ids = ["hiit_1x_week", "hiit_2x_week"]
    loaded_items = {item["id"]: item for item in load_protocol_items()}
    estimates_by_id = {
        item_id: estimate_item(
            loaded_items[item_id],
            specs[item_id],
            baseline,
            context,
            include_draws=True,
        )
        for item_id in item_ids
    }
    protocol_items = [
        {"id": "hiit_1x_week", "status": "testing"},
        {"id": "hiit_2x_week", "status": "watching"},
    ]

    result = optimize_protocol_state(
        protocol_items,
        estimates_by_id,
        specs,
        context,
        objective="qaly",
    )

    assert result["actions_from_current"]["add"] == ["hiit_2x_week"]
    assert result["actions_from_current"]["drop"] == ["hiit_1x_week"]
    assert result["actions_from_current"]["swap"] == ["hiit_1x_week->hiit_2x_week"]
    assert result["recommended_state"]["item_ids"] == ["hiit_2x_week"]


def test_protocol_optimizer_drops_negative_current_item():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    loaded_items = {item["id"]: item for item in load_protocol_items()}
    estimates_by_id = {
        "vitamin_d_2000": estimate_item(
            loaded_items["vitamin_d_2000"],
            specs["vitamin_d_2000"],
            baseline,
            context,
            include_draws=True,
        )
    }

    result = optimize_protocol_state(
        [{"id": "vitamin_d_2000", "status": "testing"}],
        estimates_by_id,
        specs,
        context,
        objective="qaly",
    )

    assert result["recommended_state"]["item_ids"] == []
    assert result["actions_from_current"]["drop"] == ["vitamin_d_2000"]
    assert result["delta_qaly"] > 0


def test_protocol_optimizer_payload_has_net_and_qaly_views():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = protocol_ground_up.resolve_protocol_context(None)
    item_ids = ["hiit_2x_week", "apap_nightly"]
    loaded_items = {item["id"]: item for item in load_protocol_items()}
    estimates_by_id = {
        item_id: estimate_item(
            loaded_items[item_id],
            specs[item_id],
            baseline,
            context,
            include_draws=True,
        )
        for item_id in item_ids
    }

    result = build_protocol_optimizers(
        [{"id": item_id, "status": "watching"} for item_id in item_ids],
        estimates_by_id,
        specs,
        context,
    )

    assert set(result) == {"net_benefit", "qaly"}
    assert result["qaly"]["recommended_state"]["total_qaly"] >= result[
        "net_benefit"
    ]["recommended_state"]["total_qaly"]


def test_estimate_item_samples_qol_overlay_uncertainty(monkeypatch):
    def fake_simulate(*args, **kwargs):
        return {
            "mortality_qaly": 0.0,
            "direct_harm_qaly": 0.0,
            "simulated_qaly": 0.0,
            "p_benefit": 0.5,
            "p_harm": 0.5,
            "qaly_draws": np.zeros(protocol_ground_up.N_SIMULATIONS),
            "profile_effect_multiplier": 1.0,
            "effective_observed_hr": 1.0,
        }

    monkeypatch.setattr(protocol_ground_up, "simulate_structured_qaly", fake_simulate)

    baseline = load_baseline()
    spec = StackSpec(
        item_id="vitamin_k2",
        observed_hr=1.0,
        log_sd=0.05,
        conf_alpha=1.0,
        conf_beta=5.0,
        qol_annual=0.001,
        qol_years=10,
        low_qaly=-0.01,
        high_qaly=0.02,
        personalization="test",
        rationale="test",
        sources=(),
    )
    item = {
        "id": "vitamin_k2",
        "name": "Vitamin K2 test",
        "status": "testing",
        "category": "supplement_bought",
        "display_category": "supplement",
        "annual_cost": 10,
    }

    estimate = estimate_item(item, spec, baseline)

    assert estimate["total_qaly"] == pytest.approx(0.0088, abs=0.0001)
    assert 0.0 < estimate["p_harm"] < 0.1
    assert 0.9 < estimate["p_benefit"] < 1.0
    assert estimate["assumptions"]["qol_uncertainty_relative_sd"] == pytest.approx(0.6)


def test_decision_rankings_split_actionable_items():
    estimates = [
        {
            "id": "free_exercise",
            "name": "Free exercise",
            "status": "watching",
            "category": "supplement_candidate",
            "display_category": "exercise",
            "annual_cost": 0,
            "modeled_total_cost": 0,
            "cost_per_qaly": None,
            "total_qaly": 0.02,
            "days": 7.3,
            "p_benefit": 0.9,
            "p_harm": 0.1,
        },
        {
            "id": "cheap_supplement",
            "name": "Cheap supplement",
            "status": "testing",
            "category": "supplement_bought",
            "display_category": "supplement",
            "annual_cost": 100,
            "modeled_total_cost": 100,
            "cost_per_qaly": 5000,
            "total_qaly": 0.02,
            "days": 7.3,
            "p_benefit": 0.9,
            "p_harm": 0.1,
        },
        {
            "id": "better_supplement",
            "name": "Better supplement",
            "status": "watching",
            "category": "supplement_candidate",
            "display_category": "supplement",
            "annual_cost": 120,
            "modeled_total_cost": 120,
            "cost_per_qaly": 3000,
            "total_qaly": 0.04,
            "days": 14.6,
            "p_benefit": 0.95,
            "p_harm": 0.05,
        },
        {
            "id": "current",
            "name": "Current",
            "status": "taking",
            "category": "supplement_current",
            "display_category": "supplement",
            "annual_cost": 50,
            "modeled_total_cost": 50,
            "cost_per_qaly": 1000,
            "total_qaly": 0.05,
            "days": 18.3,
            "p_benefit": 0.95,
            "p_harm": 0.05,
        },
        {
            "id": "bad_candidate",
            "name": "Bad candidate",
            "status": "considering",
            "category": "rx_candidate",
            "display_category": "rx",
            "annual_cost": 200,
            "modeled_total_cost": 200,
            "cost_per_qaly": None,
            "total_qaly": -0.01,
            "days": -3.7,
            "p_benefit": 0.2,
            "p_harm": 0.8,
        },
    ]

    rankings = build_decision_rankings(estimates)

    assert rankings["free_positive_actions"][0]["id"] == "free_exercise"
    assert rankings["actionable_by_cost_per_qaly"][0]["id"] == "better_supplement"
    assert rankings["supplement_candidates_by_cost_per_qaly"][0]["id"] == "better_supplement"
    assert rankings["negative_actionable"][0]["id"] == "bad_candidate"
    assert "current" not in {
        item["id"] for item in rankings["actionable_by_total_qaly"]
    }


def test_current_stack_drop_table_uses_drop_sign_convention():
    estimates = [
        {
            "id": "bad_current",
            "name": "Bad current",
            "status": "taking",
            "display_category": "supplement",
            "annual_cost": 10,
            "modeled_total_cost": 100,
            "total_qaly": -0.01,
            "p_harm": 0.8,
            "cost_per_qaly": None,
            "reference_case_status": "fallback_utility_lineage",
            "qaly_lineage": {"issues": ["direct_harm_uses_fallback_disability_weights"]},
        },
        {
            "id": "good_current",
            "name": "Good current",
            "status": "testing",
            "display_category": "supplement",
            "annual_cost": 10,
            "modeled_total_cost": 100,
            "total_qaly": 0.02,
            "p_harm": 0.1,
            "cost_per_qaly": 5000,
            "reference_case_status": "reference_case_ready",
            "qaly_lineage": {"issues": []},
        },
        {
            "id": "candidate",
            "name": "Candidate",
            "status": "watching",
            "display_category": "supplement",
            "annual_cost": 10,
            "modeled_total_cost": 100,
            "total_qaly": -0.03,
            "p_harm": 0.9,
            "cost_per_qaly": None,
            "reference_case_status": "needs_utility_lineage",
            "qaly_lineage": {"issues": []},
        },
    ]

    rows = build_current_stack_drop_table(estimates)

    assert [row["id"] for row in rows] == ["bad_current", "good_current"]
    assert rows[0]["drop_qaly"] == pytest.approx(0.01)
    assert rows[0]["p_drop_benefit"] == pytest.approx(0.8)
    assert rows[1]["drop_qaly"] == pytest.approx(-0.02)
    assert rows[1]["continue_cost_per_qaly"] == 5000


def test_joint_support_specs_gain_small_indirect_fall_pathway():
    baseline = load_baseline()
    specs = build_specs(baseline)

    assert specs["collagen_22g"].qol_annual > 0.0008 * 0.30
    assert specs["collagen_22g"].observed_hr == 1.0
    assert specs["hyaluronic_acid_120"].observed_hr == 1.0
    assert specs["ginger_400"].observed_hr == 1.0


def test_humidifier_stays_positive_but_below_stronger_airway_aids():
    baseline = load_baseline()
    specs = build_specs(baseline)

    assert specs["humidifier_nightly"].qol_annual > 0.0
    assert specs["humidifier_nightly"].qol_annual < specs["nasal_strips_nightly"].qol_annual
    assert specs["humidifier_nightly"].qol_annual < specs["nasacort_nightly"].qol_annual


def test_mouth_tape_lands_between_humidifier_and_nasal_strips():
    baseline = load_baseline()
    specs = build_specs(baseline)

    assert specs["mouth_tape_nightly"].qol_annual > specs["humidifier_nightly"].qol_annual
    assert specs["mouth_tape_nightly"].qol_annual < specs["nasal_strips_nightly"].qol_annual


def test_sleep_specs_reuse_catalog_sleep_and_airway_fields():
    baseline = load_baseline()
    specs = build_specs(baseline)

    for item_id in [
        "trazodone_50mg",
        "melatonin_300mcg",
        "nasacort_nightly",
        "nasal_strips_nightly",
        "humidifier_nightly",
        "mouth_tape_nightly",
        "head_elevation_nightly",
    ]:
        resolved = resolve_stack_spec(specs[item_id], CATALOG[item_id])
        assert resolved.sleep_component_relief == CATALOG[item_id].sleep_component_relief
        assert resolved.airway_target_weights == CATALOG[item_id].airway_target_weights

    additional_specs = build_additional_specs(baseline)
    for item_id in [
        "apap_nightly",
        "oral_appliance_custom",
        "doxepin_3mg",
        "daridorexant_25mg",
        "lemborexant_5mg",
        "suvorexant_10mg",
    ]:
        resolved = resolve_stack_spec(additional_specs[item_id], CATALOG[item_id])
        assert resolved.sleep_component_relief == CATALOG[item_id].sleep_component_relief
        assert resolved.airway_target_weights == CATALOG[item_id].airway_target_weights


def test_sleep_specs_can_stay_sparse_and_inherit_catalog_defaults():
    baseline = load_baseline()
    specs = build_protocol_specs(baseline)

    nasacort = specs["nasacort_nightly"]
    assert nasacort.observed_hr is None
    assert nasacort.log_sd is None
    assert nasacort.sleep_component_relief is None
    assert nasacort.airway_target_weights is None

    resolved = resolve_stack_spec(nasacort, CATALOG["nasacort_nightly"])
    assert resolved.observed_hr == CATALOG["nasacort_nightly"].hr_observed
    assert resolved.log_sd == CATALOG["nasacort_nightly"].log_sd
    assert resolved.conf_alpha == CATALOG["nasacort_nightly"].conf_alpha
    assert resolved.conf_beta == CATALOG["nasacort_nightly"].conf_beta
    assert resolved.sleep_component_relief == CATALOG["nasacort_nightly"].sleep_component_relief
    assert resolved.airway_target_weights == CATALOG["nasacort_nightly"].airway_target_weights


def test_apply_protocol_spec_uses_specs_directly_without_metadata_roundtrip():
    context = load_protocol_context()
    baseline = load_baseline(context)
    specs = build_protocol_specs(baseline, context)

    personalized = apply_protocol_spec(
        item_id="nasacort_nightly",
        base_entry=CATALOG["nasacort_nightly"],
        specs=specs,
        annual_cost=123.0,
    )

    resolved = resolve_stack_spec(specs["nasacort_nightly"], CATALOG["nasacort_nightly"])

    assert personalized.hr_observed == resolved.observed_hr
    assert personalized.qol_annual == resolved.qol_annual
    assert personalized.annual_cost == 123.0
    assert personalized.notes == resolved.rationale
