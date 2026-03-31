"""Scenario-level regression tests for canonical model behavior."""

from __future__ import annotations

import json
from pathlib import Path

from optiqal import (
    AnalysisConfig,
    CATALOG,
    Profile,
    analyze,
    build_public_sleep_decision_specs,
    build_stack_interaction_penalty_fn,
    evaluate_decision_states,
    serialize_decision_state_evaluations,
)
from optiqal.sleep import (
    SleepMetrics,
    SleepStudyResult,
    apply_sleep_study,
    estimate_sleep_burden,
)


FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "model_regression.json").read_text()
)
SUBSET_IDS = [
    "apap_nightly",
    "oral_appliance_custom",
    "nasacort_nightly",
    "nasal_strips_nightly",
    "head_elevation_nightly",
    "humidifier_nightly",
    "mouth_tape_nightly",
    "trazodone_50mg",
    "doxepin_3mg",
    "daridorexant_25mg",
    "lemborexant_5mg",
    "suvorexant_10mg",
]


def canonical_profile() -> Profile:
    return Profile(
        age=39,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="active",
    )


def canonical_wearable_sleep_estimate():
    return estimate_sleep_burden(
        SleepMetrics(
            duration_hours=6.6,
            recovery_score=58.0,
            sleep_quality_score=82.0,
            waso_min=10.0,
            routine_score=78.0,
            social_jetlag_min=22.0,
            latency_min=18.0,
            breathing_score=0.92,
            spo2=96.1,
            snore_pct=1.0,
            airway_response_signal=0.40,
        )
    )


def canonical_confirmed_mild_osa_estimate():
    return apply_sleep_study(
        canonical_wearable_sleep_estimate(),
        SleepStudyResult(
            study_type="home",
            rei=7.7,
            mean_spo2=97.0,
            nadir_spo2=94.0,
            total_sleep_hours=7.1,
            obstructive_apneas=35,
            hypopneas=19,
            central_apneas=0,
            mixed_apneas=0,
            supine_fraction=0.52,
            supine_rei=5.2,
            used_nasal_steroid=True,
            used_nasal_strips=True,
        ),
    )


def subset_entries():
    return {
        item_id: CATALOG[item_id]
        for item_id in SUBSET_IDS
    }


def run_subset_analysis(sleep_estimate):
    return analyze(
        AnalysisConfig(
            profile=canonical_profile(),
            sleep_estimate=sleep_estimate,
            n_simulations=2000,
            random_state=42,
        ),
        catalog_entries=subset_entries(),
    )


def assert_between(actual: float, bounds: list[float], label: str) -> None:
    low, high = bounds
    assert low <= actual <= high, f"{label} expected in [{low}, {high}], got {actual}"


def test_confirmed_mild_osa_reweights_airway_choices_directionally():
    wearable = run_subset_analysis(canonical_wearable_sleep_estimate())
    confirmed = run_subset_analysis(canonical_confirmed_mild_osa_estimate())

    wearable_by_id = wearable.item_results_by_id
    confirmed_by_id = confirmed.item_results_by_id

    assert wearable_by_id["daridorexant_25mg"]["total_qaly"] > wearable_by_id["apap_nightly"]["total_qaly"]
    assert confirmed_by_id["apap_nightly"]["total_qaly"] > confirmed_by_id["daridorexant_25mg"]["total_qaly"]
    assert confirmed_by_id["apap_nightly"]["total_qaly"] > wearable_by_id["apap_nightly"]["total_qaly"] * 5
    assert confirmed_by_id["oral_appliance_custom"]["total_qaly"] > wearable_by_id["oral_appliance_custom"]["total_qaly"] * 5
    assert confirmed_by_id["nasacort_nightly"]["total_qaly"] > wearable_by_id["nasacort_nightly"]["total_qaly"] * 4


def test_canonical_sleep_subset_matches_golden_ranges():
    scenarios = {
        "wearable_only_subset": canonical_wearable_sleep_estimate(),
        "confirmed_mild_osa_subset": canonical_confirmed_mild_osa_estimate(),
    }

    for scenario_name, sleep_estimate in scenarios.items():
        fixture = FIXTURES[scenario_name]
        result = run_subset_analysis(sleep_estimate)
        ordered_ids = [
            row["id"]
            for row in sorted(
                result.item_results,
                key=lambda row: row["total_qaly"],
                reverse=True,
            )
        ]
        expected_prefix = fixture["ordered_ids_prefix"]
        assert ordered_ids[: len(expected_prefix)] == expected_prefix

        for item_id, field_ranges in fixture["items"].items():
            row = result.item_results_by_id[item_id]
            for field, bounds in field_ranges.items():
                assert_between(row[field], bounds, f"{scenario_name}.{item_id}.{field}")


def test_public_sleep_decision_states_match_golden_ranges():
    fixture = FIXTURES["public_sleep_decision_states_confirmed_mild_osa"]
    analysis = run_subset_analysis(canonical_confirmed_mild_osa_estimate())
    single_qalys = {
        item_id: row["total_qaly"]
        for item_id, row in analysis.item_results_by_id.items()
    }
    annual_costs = {
        item_id: row["annual_cost"]
        for item_id, row in analysis.item_results_by_id.items()
    }
    cost_values = {
        item_id: row["total_cost"]
        for item_id, row in analysis.item_results_by_id.items()
    }
    entries = subset_entries()
    exclusive_groups = {
        item_id: entry.exclusive_group
        for item_id, entry in entries.items()
        if entry.exclusive_group
    }
    stack_penalty_fn = build_stack_interaction_penalty_fn(
        entries,
        analysis.config.profile,
        analysis.config.qaly_discount_rate,
        single_qalys,
        analysis.config.sleep_overlap_multipliers,
    )
    serialized = serialize_decision_state_evaluations(
        evaluate_decision_states(
            build_public_sleep_decision_specs(),
            single_qalys=single_qalys,
            annual_costs=annual_costs,
            cost_values=cost_values,
            horizon_years=analysis.config.horizon_years,
            stack_interaction_penalty_fn=stack_penalty_fn,
            total_cost_value_fn=lambda item_ids: sum(cost_values[item_id] for item_id in item_ids),
            exclusive_groups=exclusive_groups,
        ),
        item_name_by_id={item_id: entry.name for item_id, entry in entries.items()},
    )

    for state_id, expected_prefix in fixture["ordered_option_prefix_by_state"].items():
        actual_ids = [option["id"] for option in serialized[state_id]["options"]]
        assert actual_ids[: len(expected_prefix)] == expected_prefix

    for state_id, options in fixture["ranges"].items():
        actual_by_id = {
            option["id"]: option
            for option in serialized[state_id]["options"]
        }
        for option_id, field_ranges in options.items():
            for field, bounds in field_ranges.items():
                assert_between(
                    actual_by_id[option_id][field],
                    bounds,
                    f"{state_id}.{option_id}.{field}",
                )
