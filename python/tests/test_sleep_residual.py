"""The bedtime residual rule removes duplicate benefits consistently."""

from dataclasses import replace

import numpy as np
import pytest

import optiqal.protocol_ground_up as protocol
from optiqal.catalog import CATALOG, simulate_catalog
from optiqal.protocol_personalization import protocol_metadata_from_specs
from optiqal.qol_annotations import general_qol_evidence_for
from optiqal.sleep_residual import (
    EXISTING_NON_BEDTIME_SLEEP_RESIDUAL_ITEMS,
    SLEEP_ONLY_RESIDUAL_ITEMS,
    apply_sleep_residual_rule,
)


def test_named_rule_covers_the_adjudicated_bedtime_items():
    assert SLEEP_ONLY_RESIDUAL_ITEMS == {
        "trazodone_50mg",
        "doxepin_3mg",
        "daridorexant_25mg",
        "lemborexant_5mg",
        "suvorexant_10mg",
        "melatonin_300mcg",
        "magnesium_200",
        "glycine_2g",
        "apigenin_50",
        "l_theanine_200_bedtime",
    }


@pytest.mark.parametrize("item_id", sorted(SLEEP_ONLY_RESIDUAL_ITEMS))
def test_adjudicated_sleep_items_have_no_positive_general_residual(item_id):
    assert apply_sleep_residual_rule(item_id, 0.001) == 0.0
    assert (
        apply_sleep_residual_rule(
            item_id, 0.001, sleep_component_relief={"quality": 0.2}
        )
        == 0.0
    )


@pytest.mark.parametrize("item_id", sorted(SLEEP_ONLY_RESIDUAL_ITEMS))
def test_authored_mode_restores_the_exact_authored_residual(item_id):
    authored = 0.001234567891
    assert (
        apply_sleep_residual_rule(
            item_id,
            authored,
            "authored",
            sleep_component_relief={"quality": 0.2},
        )
        == authored
    )


def test_new_sleep_items_default_to_no_duplicate_residual():
    relief = {"quality": 0.2, "duration": 0.1}
    original = dict(relief)
    assert (
        apply_sleep_residual_rule(
            "new_sleep_candidate", 0.002, sleep_component_relief=relief
        )
        == 0.0
    )
    assert relief == original
    assert (
        apply_sleep_residual_rule(
            "new_sleep_candidate", 0.002, "authored", sleep_component_relief=relief
        )
        == 0.002
    )


def test_ashwagandha_retains_its_distinct_stress_residual():
    assert (
        apply_sleep_residual_rule(
            "ashwagandha_600", 0.001, sleep_component_relief={"quality": 0.12}
        )
        == 0.001
    )


@pytest.mark.parametrize("item_id", sorted(EXISTING_NON_BEDTIME_SLEEP_RESIDUAL_ITEMS))
def test_existing_non_bedtime_items_stay_outside_this_residual_review(item_id):
    assert (
        apply_sleep_residual_rule(
            item_id, 0.001, sleep_component_relief={"breathing": 0.2}
        )
        == 0.001
    )


def test_non_sleep_items_keep_general_qol_benefits():
    assert apply_sleep_residual_rule("non_sleep_item", 0.002) == 0.002
    assert (
        apply_sleep_residual_rule("non_sleep_item", 0.002, sleep_component_relief={})
        == 0.002
    )


@pytest.mark.parametrize("item_id", ["trazodone_50mg", "new_sleep_candidate"])
def test_sleep_rule_never_erases_authored_general_qol_harm(item_id):
    assert (
        apply_sleep_residual_rule(
            item_id, -0.001, sleep_component_relief={"quality": 0.2}
        )
        == -0.001
    )


@pytest.mark.parametrize("authored", [-0.001, 0.0, 0.001])
def test_invalid_residual_mode_fails_before_evaluation(authored):
    with pytest.raises(ValueError, match="Unknown sleep residual mode"):
        apply_sleep_residual_rule("trazodone_50mg", authored, "invalid")


@pytest.fixture(scope="module")
def protocol_residual_inputs():
    context = protocol.resolve_protocol_context()
    baseline = protocol.load_baseline(context)
    specs = protocol.build_specs(baseline, context)
    specs.update(protocol.build_additional_specs(baseline, context))
    items = {item["id"]: item for item in protocol.load_protocol_items(context)}
    return context, baseline, specs, items


@pytest.mark.parametrize("item_id", sorted(SLEEP_ONLY_RESIDUAL_ITEMS))
def test_protocol_residual_switch_restores_authored_benefit_and_lineage(
    item_id, protocol_residual_inputs, monkeypatch
):
    monkeypatch.setattr(protocol, "N_SIMULATIONS", 256)
    context, baseline, specs, items = protocol_residual_inputs
    assert context.residual_mode == "evidence_rule"
    resolved = protocol.resolve_stack_spec(specs[item_id], CATALOG[item_id])
    corrected = protocol.estimate_item(
        items[item_id], specs[item_id], baseline, context, include_draws=True
    )
    authored = protocol.estimate_item(
        items[item_id],
        specs[item_id],
        baseline,
        replace(context, residual_mode="authored"),
        include_draws=True,
    )

    assert corrected["assumptions"]["qol_annual"] == 0.0
    assert corrected["qol_evidence"]["general_qol"] is None
    assert corrected["qol_evidence"]["general_qol_claimed_qaly"] == 0.0
    assert corrected["general_qol_qaly"] == 0.0
    general_lineage = corrected["qaly_lineage"]["components"]["general_qol"]
    assert general_lineage["utility_lineage"] == {}
    assert general_lineage["reference_case_status"] == "not_applicable"

    assert authored["assumptions"]["qol_annual"] == round(resolved.qol_annual, 6)
    assert authored["assumptions"]["residual_mode"] == "authored"
    claimed = resolved.qol_annual * protocol.discount_factor(resolved.qol_years)
    assert authored["qol_evidence"]["general_qol_claimed_qaly"] == round(claimed, 4)
    evidence = general_qol_evidence_for(item_id, residual_mode="authored")
    guarded = (
        claimed * evidence.multiplier_mean if evidence and claimed > 0 else claimed
    )
    assert authored["general_qol_qaly"] == round(guarded, 4)
    if claimed > 0:
        assert authored["qol_evidence"]["general_qol"] is not None
    assert np.mean(
        authored["_total_draws"] - corrected["_total_draws"]
    ) == pytest.approx(guarded, abs=1e-12)
    # The policy changes only the duplicate general-QoL benefit.
    assert authored["sleep_qol_qaly"] == corrected["sleep_qol_qaly"]
    assert authored["mortality_qaly"] == corrected["mortality_qaly"]
    assert authored["direct_harm_qaly"] == corrected["direct_harm_qaly"]


def test_protocol_ashwagandha_retains_guarded_stress_evidence(
    protocol_residual_inputs, monkeypatch
):
    monkeypatch.setattr(protocol, "N_SIMULATIONS", 256)
    context, baseline, specs, items = protocol_residual_inputs
    estimate = protocol.estimate_item(
        items["ashwagandha_600"], specs["ashwagandha_600"], baseline, context
    )
    evidence = estimate["qol_evidence"]["general_qol"]
    assert estimate["general_qol_qaly"] > 0
    assert evidence["study_quality"] == "supplement_industry_rct"
    assert evidence["category"] == "mood_stress"
    assert estimate["qaly_lineage"]["components"]["general_qol"]["utility_lineage"]


def test_protocol_context_rejects_unknown_residual_mode(protocol_residual_inputs):
    context, baseline, specs, items = protocol_residual_inputs
    with pytest.raises(ValueError, match="Unknown sleep residual mode"):
        protocol.estimate_item(
            items["trazodone_50mg"],
            specs["trazodone_50mg"],
            baseline,
            replace(context, residual_mode="invalid"),
        )


def test_metabolic_intervention_keeps_non_sleep_benefit_when_it_has_sleep_relief(
    protocol_residual_inputs, monkeypatch
):
    monkeypatch.setattr(protocol, "N_SIMULATIONS", 256)
    context, baseline, _, items = protocol_residual_inputs
    obese = replace(context, profile=replace(context.profile, bmi_category="obese"))
    spec = protocol.build_additional_specs(baseline, obese)["semaglutide"]
    resolved = protocol.resolve_stack_spec(spec, CATALOG["semaglutide"])
    assert resolved.qol_annual > 0
    assert resolved.sleep_component_relief
    estimate = protocol.estimate_item(items["semaglutide"], spec, baseline, obese)
    assert estimate["assumptions"]["qol_annual"] == round(resolved.qol_annual, 6)
    assert estimate["general_qol_qaly"] > 0


@pytest.mark.parametrize("item_id", sorted(SLEEP_ONLY_RESIDUAL_ITEMS))
def test_catalog_uses_the_same_residual_rule_without_changing_authored_fields(item_id):
    entry = CATALOG[item_id]
    authored = entry.qol_annual
    assert entry.raw_qol_annual() == 0.0
    assert entry.effective_qol_annual() == 0.0
    assert entry.raw_qol_annual("authored") == authored
    evidence = general_qol_evidence_for(item_id, residual_mode="authored")
    expected = authored * evidence.multiplier_mean if evidence else 0.0
    assert entry.effective_qol_annual("authored") == pytest.approx(expected, abs=1e-12)
    assert entry.qol_annual == authored


def test_catalog_simulation_can_restore_authored_sleep_residual(
    protocol_residual_inputs,
):
    context, baseline, _, _ = protocol_residual_inputs
    entry = CATALOG["trazodone_50mg"]
    kwargs = {
        "profile": context.profile,
        "n_simulations": 256,
        "catalog_entries": {entry.id: entry},
        "sleep_estimate": protocol.protocol_sleep_estimate_from_baseline_dict(baseline),
    }
    corrected = simulate_catalog(**kwargs)[0]
    authored = simulate_catalog(**kwargs, residual_mode="authored")[0]
    assert corrected["raw_qol_qaly"] == 0.0
    assert corrected["qol_qaly"] == 0.0
    assert corrected["residual_mode"] == "evidence_rule"
    assert authored["raw_qol_qaly"] > 0
    assert authored["qol_qaly"] > 0
    assert authored["residual_mode"] == "authored"
    assert authored["total_qaly"] - corrected["total_qaly"] == pytest.approx(
        authored["qol_qaly"], abs=1e-12
    )


@pytest.mark.parametrize("item_id", sorted(SLEEP_ONLY_RESIDUAL_ITEMS))
def test_exported_metadata_separates_effective_and_authored_sleep_residuals(
    item_id, protocol_residual_inputs
):
    _, _, specs, _ = protocol_residual_inputs
    selected = {item_id: specs[item_id]}
    resolved = protocol.resolve_stack_spec(specs[item_id], CATALOG[item_id])
    effective = protocol_metadata_from_specs(selected)[item_id]["assumptions"]
    authored = protocol_metadata_from_specs(selected, residual_mode="authored")[
        item_id
    ]["assumptions"]

    assert effective["qol_annual"] == 0.0
    assert effective["authored_qol_annual"] == resolved.qol_annual
    assert effective["residual_mode"] == "evidence_rule"
    assert authored["qol_annual"] == resolved.qol_annual
    assert authored["authored_qol_annual"] == resolved.qol_annual
    assert authored["residual_mode"] == "authored"
    assert protocol.resolve_stack_spec(specs[item_id], CATALOG[item_id]) == resolved


def test_exported_metadata_keeps_ashwagandha_stress_residual(protocol_residual_inputs):
    _, _, specs, _ = protocol_residual_inputs
    metadata = protocol_metadata_from_specs(
        {"ashwagandha_600": specs["ashwagandha_600"]}
    )
    assumptions = metadata["ashwagandha_600"]["assumptions"]
    assert assumptions["qol_annual"] > 0.0
    assert assumptions["qol_annual"] == assumptions["authored_qol_annual"]


def test_exported_metadata_rejects_unknown_residual_mode(protocol_residual_inputs):
    _, _, specs, _ = protocol_residual_inputs
    with pytest.raises(ValueError, match="Unknown sleep residual mode"):
        protocol_metadata_from_specs(
            {"trazodone_50mg": specs["trazodone_50mg"]}, residual_mode="invalid"
        )
