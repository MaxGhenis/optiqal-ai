"""Tests for the QoL evidence guard stack."""

import numpy as np
import pytest

from optiqal.catalog import CATALOG
from optiqal.protocol_ground_up import (
    _evidence_scaled_draws,
    build_additional_specs,
    build_specs,
    estimate_item,
    load_baseline,
    load_protocol_items,
    resolve_stack_spec,
)
from optiqal.qol_annotations import (
    GENERAL_QOL_EVIDENCE,
    SLEEP_RELIEF_EVIDENCE,
    general_qol_evidence_for,
    sleep_relief_evidence_for,
)
from optiqal.qol_evidence import (
    AUTHORED_RESIDUAL_OPTIMISM_PRIOR,
    QOL_STUDY_QUALITY_SHRINKAGE,
    QOL_TRANSPORT_PRIORS,
    QolEvidence,
    guarded_component_relief,
    stable_seed,
)
from optiqal.sleep import (
    sleep_intervention_mortality_hr_multiplier,
)


def test_every_positive_general_qol_claim_is_annotated():
    """Silent legacy fallback would defeat the point of the guard."""
    missing = [
        item_id
        for item_id, entry in CATALOG.items()
        if entry.qol_annual > 0 and item_id not in GENERAL_QOL_EVIDENCE
    ]
    assert missing == []


def test_every_sleep_relief_claim_is_annotated():
    missing = [
        item_id
        for item_id, entry in CATALOG.items()
        if entry.sleep_component_relief and item_id not in SLEEP_RELIEF_EVIDENCE
    ]
    assert missing == []


def test_every_positive_spec_level_claim_is_annotated():
    baseline = load_baseline()
    specs = dict(build_specs(baseline))
    specs.update(build_additional_specs(baseline))
    missing = []
    for item_id, spec in specs.items():
        resolved = resolve_stack_spec(spec, CATALOG.get(item_id))
        if resolved.qol_annual > 0 and item_id not in GENERAL_QOL_EVIDENCE:
            missing.append(item_id)
        if resolved.sleep_component_relief and item_id not in SLEEP_RELIEF_EVIDENCE:
            missing.append(f"{item_id} (sleep)")
    assert missing == []


def test_shrinkage_tiers_are_monotone_and_bounded():
    ordered = [
        "rct_objective_endpoint",
        "meta_analysis_placebo_rcts",
        "rct_placebo_patient_reported",
        "rct_open_label",
        "supplement_industry_rct",
        "observational_symptom",
        "mechanistic_or_self_experiment",
    ]
    values = [QOL_STUDY_QUALITY_SHRINKAGE[tier] for tier in ordered]
    assert values == sorted(values)
    assert all(0.0 < v < 1.0 for v in values)


def test_transport_priors_are_skeptical_and_ordered():
    means = {cat: prior.mean for cat, prior in QOL_TRANSPORT_PRIORS.items()}
    assert all(0.0 < m < 0.75 for m in means.values())
    # Objective-adjacent categories should retain more than diffuse ones.
    assert means["fitness_function"] > means["sleep_symptom"]
    assert means["sexual_function"] > means["mood_stress"]
    assert means["general_vitality"] == min(means.values())


def test_anchor_modes_compose_correctly():
    authored = QolEvidence("supplement_industry_rct", "sleep_symptom")
    published = QolEvidence(
        "supplement_industry_rct", "sleep_symptom", "published_delta"
    )
    assert authored.multiplier_mean == pytest.approx(
        0.5 * AUTHORED_RESIDUAL_OPTIMISM_PRIOR.mean
    )
    assert published.multiplier_mean == pytest.approx(
        0.5 * QOL_TRANSPORT_PRIORS["sleep_symptom"].mean
    )
    # authored_shaded must always be the milder guard (no double-shrink).
    assert authored.multiplier_mean > published.multiplier_mean


def test_guarded_relief_scales_fractions_and_passes_through_unannotated():
    relief = {"breathing": 0.2, "quality": 0.1}
    ev = QolEvidence("rct_objective_endpoint", "respiratory_airway", "published_delta")
    guarded = guarded_component_relief(relief, ev)
    assert guarded["breathing"] == pytest.approx(0.2 * ev.multiplier_mean)
    assert guarded_component_relief(relief, None) == relief


def test_sleep_guard_reaches_the_mortality_multiplier():
    """The relief-derived hazard multiplier must inherit the evidence guard."""
    baseline = load_baseline()
    items = {item["id"]: item for item in load_protocol_items()}
    specs = dict(build_specs(baseline))
    specs.update(build_additional_specs(baseline))
    estimate = estimate_item(items["apap_nightly"], specs["apap_nightly"], baseline)
    guarded_mult = estimate["assumptions"]["sleep_mortality_hr_multiplier"]

    # Reconstruct the unguarded multiplier from the same baseline.
    from optiqal.protocol_ground_up import (
        protocol_sleep_estimate_from_baseline_dict,
    )

    sleep_estimate = protocol_sleep_estimate_from_baseline_dict(baseline)
    from optiqal.sleep import effective_sleep_component_relief

    resolved = resolve_stack_spec(specs["apap_nightly"], CATALOG["apap_nightly"])
    raw_relief = effective_sleep_component_relief(
        sleep_estimate,
        resolved.sleep_component_relief,
        resolved.airway_target_weights,
    )
    unguarded_mult = sleep_intervention_mortality_hr_multiplier(
        sleep_estimate, raw_relief
    )
    # Guarded relief is smaller, so the multiplier sits closer to 1.0.
    assert unguarded_mult < guarded_mult < 1.0


def test_catalog_relief_uses_guard_as_replacement_not_stack():
    entry = CATALOG["apap_nightly"]
    ev = sleep_relief_evidence_for("apap_nightly")
    assert ev is not None
    baseline = load_baseline()
    from optiqal.catalog import _sleep_component_relief_effect
    from optiqal.protocol_ground_up import (
        protocol_sleep_estimate_from_baseline_dict,
    )

    sleep_estimate = protocol_sleep_estimate_from_baseline_dict(baseline)
    raw = _sleep_component_relief_effect(
        sleep_estimate,
        entry.sleep_component_relief,
        entry.airway_target_weights,
    )
    effective = entry._effective_sleep_component_relief(sleep_estimate)
    for component, value in effective.items():
        assert value == pytest.approx(raw[component] * ev.multiplier_mean)


def test_estimate_item_guards_positive_claims_only():
    baseline = load_baseline()
    items = {item["id"]: item for item in load_protocol_items()}
    specs = dict(build_specs(baseline))
    specs.update(build_additional_specs(baseline))

    guarded = estimate_item(items["magnesium_200"], specs["magnesium_200"], baseline)
    ev = general_qol_evidence_for("magnesium_200")
    claimed = guarded["qol_evidence"]["general_qol_claimed_qaly"]
    assert claimed > 0
    assert guarded["general_qol_qaly"] == pytest.approx(
        claimed * ev.multiplier_mean, abs=1e-3
    )
    assert guarded["qol_evidence"]["general_qol"]["study_quality"] == (
        "supplement_industry_rct"
    )

    negative = estimate_item(items["semaglutide"], specs["semaglutide"], baseline)
    neg_claimed = negative["qol_evidence"]["general_qol_claimed_qaly"]
    assert neg_claimed < 0
    assert negative["general_qol_qaly"] == pytest.approx(neg_claimed, abs=1e-4)
    assert negative["qol_evidence"]["general_qol"] is None


def test_evidence_scaled_draws_preserve_the_guarded_mean():
    ev = QolEvidence("supplement_industry_rct", "sleep_symptom", "published_delta")
    draws = _evidence_scaled_draws(
        0.01,
        item_id="unit_test_item",
        component="general_qol",
        evidence_quality="moderate",
        evidence=ev,
        n_simulations=20_000,
    )
    assert float(np.mean(draws)) == pytest.approx(0.01, abs=1e-12)
    # Transport-prior spread should widen the draws vs the unguarded path.
    plain = _evidence_scaled_draws(
        0.01,
        item_id="unit_test_item",
        component="general_qol",
        evidence_quality="moderate",
        evidence=None,
        n_simulations=20_000,
    )
    assert float(np.std(draws)) > float(np.std(plain))


def test_stable_seed_is_deterministic_and_distinct():
    assert stable_seed("a", "b") == stable_seed("a", "b")
    assert stable_seed("a", "b") != stable_seed("a", "c")


def test_predeclared_ranges_match_the_frozen_file():
    """Editing a spec range must show up as a diff in the frozen data file.

    This is the discipline that makes the within-range sanity check a real
    precommitment: you cannot move a goalpost and the model in the same edit
    without the freeze file changing too.
    """
    from optiqal.protocol_ground_up import load_predeclared_ranges

    frozen = load_predeclared_ranges()["ranges"]
    baseline = load_baseline()
    specs = dict(build_specs(baseline))
    specs.update(build_additional_specs(baseline))

    assert set(frozen) == set(specs)
    for item_id, spec in specs.items():
        resolved = resolve_stack_spec(spec, CATALOG.get(item_id))
        assert frozen[item_id][0] == pytest.approx(resolved.low_qaly), item_id
        assert frozen[item_id][1] == pytest.approx(resolved.high_qaly), item_id
