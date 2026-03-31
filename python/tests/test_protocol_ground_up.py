"""Tests for personalized ground-up protocol assumptions."""

from optiqal.catalog import CATALOG
from optiqal.protocol_personalization import (
    apply_protocol_spec,
    build_protocol_specs,
    load_protocol_context,
    load_protocol_profile,
)
from optiqal.protocol_ground_up import (
    PROFILE,
    StackSpec,
    apply_joint_fall_pathway,
    build_additional_specs,
    build_specs,
    load_baseline,
    resolve_stack_spec,
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
