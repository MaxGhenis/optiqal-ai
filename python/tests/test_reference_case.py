"""Tests for reference-case QALY utilities."""

import pytest

from optiqal.reference_case import (
    DEFAULT_REFERENCE_CASE,
    PUBLIC_HEALTH_UTILITY_WEIGHTS,
    MorbidityEffect,
    UtilityWeight,
    discounted_years,
    get_public_health_utility_weight,
    morbidity_qaly,
    morbidity_qaly_breakdown,
    utility_reference_case_status,
)


def test_default_reference_case_uses_second_panel_style_discounting():
    assert DEFAULT_REFERENCE_CASE.health_discount_rate == pytest.approx(0.03)
    assert DEFAULT_REFERENCE_CASE.cost_discount_rate == pytest.approx(0.03)
    assert DEFAULT_REFERENCE_CASE.reporting_standard == "CHEERS 2022"
    assert DEFAULT_REFERENCE_CASE.utility_preference_order[0] == "eq_5d"


def test_discounted_years_handles_fractional_durations():
    assert discounted_years(0, 0.03) == 0
    assert discounted_years(1, 0.03) == pytest.approx(1.0)
    assert discounted_years(2.5, 0.03) == pytest.approx(1 + 1 / 1.03 + 0.5 / 1.03**2)


def test_utility_weight_converts_utility_and_disutility_to_decrement():
    eq5d_utility = UtilityWeight(
        id="mild_symptom_eq5d",
        label="Mild symptom utility",
        value=0.9,
        value_type="utility",
        instrument="eq_5d",
        source_url="https://example.com/eq5d",
    )
    gbd_weight = UtilityWeight(
        id="mild_symptom_gbd",
        label="Mild symptom disutility",
        value=0.1,
        value_type="disutility",
        instrument="gbd_disability_weight",
        source_url="https://example.com/gbd",
    )

    assert eq5d_utility.utility_decrement == pytest.approx(0.1)
    assert eq5d_utility.reference_case_status == "reference_case"
    assert gbd_weight.utility_decrement == pytest.approx(0.1)
    assert gbd_weight.reference_case_status == "fallback"


def test_morbidity_qaly_signs_for_caused_and_avoided_health_states():
    weights = {
        "symptom": UtilityWeight(
            id="symptom",
            label="Symptom disutility",
            value=0.2,
            value_type="disutility",
            instrument="eq_5d",
            source_url="https://example.com/symptom",
        )
    }
    caused = MorbidityEffect(
        id="caused_symptom",
        utility_weight_id="symptom",
        probability=0.5,
        duration_years=2,
        direction="cause",
    )
    avoided = MorbidityEffect(
        id="avoided_symptom",
        utility_weight_id="symptom",
        probability=0.5,
        duration_years=2,
        direction="avoid",
    )

    expected = (
        0.5 * 0.2 * discounted_years(2, DEFAULT_REFERENCE_CASE.health_discount_rate)
    )
    assert morbidity_qaly(caused, weights) == pytest.approx(-expected)
    assert morbidity_qaly(avoided, weights) == pytest.approx(expected)


def test_morbidity_qaly_breakdown_reports_lineage():
    weights = {
        "symptom": UtilityWeight(
            id="symptom",
            label="Symptom disutility",
            value=0.2,
            value_type="disutility",
            instrument="mapping",
            source_url="https://example.com/mapped",
        )
    }
    effect = MorbidityEffect(
        id="avoided_symptom",
        utility_weight_id="symptom",
        probability=1.0,
        duration_years=1,
        direction="avoid",
    )

    breakdown = morbidity_qaly_breakdown((effect,), weights)

    assert breakdown["reference_case"] == DEFAULT_REFERENCE_CASE.id
    assert breakdown["total_qaly"] == pytest.approx(0.2)
    assert breakdown["effects"][0]["reference_case_status"] == "acceptable_mapped"


def test_utility_reference_case_status_flags_personal_utility():
    assert utility_reference_case_status("eq_5d") == "reference_case"
    assert utility_reference_case_status("mapping") == "acceptable_mapped"
    assert utility_reference_case_status("gbd_disability_weight") == "fallback"
    assert utility_reference_case_status("personal_utility") == "non_reference_case"


def test_public_health_utility_weights_have_uncertainty_and_lineage():
    insomnia = get_public_health_utility_weight(
        "insomnia_disability_weight_europe_2015"
    )
    sleep_apnoea = PUBLIC_HEALTH_UTILITY_WEIGHTS[
        "sleep_apnoea_disability_weight_europe_2015"
    ]
    sexual_function = get_public_health_utility_weight(
        "erectile_dysfunction_tto_utility_gain_stolk_2000"
    )
    hair_proxy = get_public_health_utility_weight("mild_alopecia_areata_tto_proxy_2024")
    anxiety = get_public_health_utility_weight(
        "anxiety_disorders_mild_disability_weight_europe_2015"
    )
    acute_moderate = get_public_health_utility_weight(
        "infectious_disease_acute_episode_moderate_disability_weight_europe_2015"
    )

    assert insomnia.utility_decrement == pytest.approx(0.023)
    assert insomnia.lower == pytest.approx(0.017)
    assert insomnia.upper == pytest.approx(0.028)
    assert insomnia.reference_case_status == "fallback"
    assert sleep_apnoea.utility_decrement == pytest.approx(0.036)
    assert "30,660" in str(sleep_apnoea.population)
    assert sexual_function.utility_decrement == pytest.approx(0.11)
    assert sexual_function.reference_case_status == "reference_case"
    assert hair_proxy.utility_decrement == pytest.approx(0.081)
    assert hair_proxy.reference_case_status == "acceptable_mapped"
    assert anxiety.utility_decrement == pytest.approx(0.045)
    assert acute_moderate.utility_decrement == pytest.approx(0.051)
    assert acute_moderate.reference_case_status == "fallback"
