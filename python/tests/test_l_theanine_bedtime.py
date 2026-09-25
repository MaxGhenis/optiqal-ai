"""The standalone bedtime L-theanine item and its provisional parameters."""

from __future__ import annotations

import pytest

from optiqal import provisional_params as provisional
from optiqal.catalog import CATALOG
from optiqal.confounding import CATEGORY_PRIORS
from optiqal.protocol_ground_up import (
    ITEMS_ADDED_AFTER_RANGE_FREEZE,
    build_additional_specs,
    build_specs,
    estimate_item,
    load_baseline,
    load_predeclared_ranges,
    load_protocol_items,
    modeled_total_cost,
    predeclared_range_drift,
    resolve_protocol_context,
    resolve_stack_spec,
)
from optiqal.qol_annotations import general_qol_evidence_for, sleep_relief_evidence_for
from optiqal.sleep import SLEEP_COMPONENT_BENEFIT_TAGS
from optiqal.sleep_stack import select_sleep_stack_universe

ITEM = "l_theanine_200_bedtime"


def test_catalog_entry_reads_the_provisional_parameters():
    assert provisional.L_THEANINE_BEDTIME_ID == ITEM
    entry = CATALOG[ITEM]
    assert entry.name == "L-Theanine 200mg bedtime"
    assert entry.category == "supplement_current"
    assert entry.annual_cost == 60.0
    assert entry.bundle_id is None
    assert entry.hr_observed == provisional.L_THEANINE_BEDTIME_HR == 1.0
    assert entry.has_direct_mortality_effect is False
    assert entry.qol_annual == provisional.L_THEANINE_BEDTIME_QOL_ANNUAL
    assert entry.qol_years == provisional.L_THEANINE_BEDTIME_QOL_YEARS
    assert dict(entry.sleep_component_relief) == (
        provisional.L_THEANINE_BEDTIME_SLEEP_COMPONENT_RELIEF
    )
    assert entry.benefit_tags == [
        SLEEP_COMPONENT_BENEFIT_TAGS[component]
        for component in provisional.L_THEANINE_BEDTIME_SLEEP_COMPONENT_RELIEF
    ]
    assert tuple(entry.interaction_tags) == (
        provisional.L_THEANINE_BEDTIME_INTERACTION_TAGS
    )
    # No study is linked, so nothing is cited.
    assert entry.sources == []
    assert entry.study_ids == []


def test_prior_is_the_category_fallback_not_a_new_judgment():
    entry = CATALOG[ITEM]
    fallback = CATEGORY_PRIORS["other"]
    assert (entry.conf_alpha, entry.conf_beta) == (fallback.alpha, fallback.beta)


def test_distinct_from_the_longevity_mix_theanine():
    morning = CATALOG["l_theanine_200"]
    assert morning.bundle_id == "blueprint_longevity_mix"
    assert morning.qol_annual == pytest.approx(0.0004)
    assert CATALOG[ITEM].bundle_id is None
    assert CATALOG[ITEM].name != morning.name


def test_qol_guard_annotations_use_the_provisional_tier():
    # The default sleep residual rule gives bedtime items no general-QoL
    # credit, so the authored annotation is reachable only in "authored" mode.
    assert general_qol_evidence_for(ITEM) is None
    for evidence, anchor in (
        (general_qol_evidence_for(ITEM, residual_mode="authored"), "authored_shaded"),
        (sleep_relief_evidence_for(ITEM), "published_delta"),
    ):
        assert evidence is not None
        assert (
            evidence.study_quality == provisional.L_THEANINE_BEDTIME_QOL_STUDY_QUALITY
        )
        assert evidence.category == provisional.L_THEANINE_BEDTIME_QOL_CATEGORY
        assert evidence.anchor == anchor


def test_spec_is_sparse_and_the_estimate_is_sleep_only():
    context = resolve_protocol_context(None)
    baseline = load_baseline(context)
    specs = build_specs(baseline, context)
    specs.update(build_additional_specs(baseline, context))
    resolved = resolve_stack_spec(specs[ITEM], CATALOG[ITEM])
    assert (resolved.low_qaly, resolved.high_qaly) == (
        provisional.L_THEANINE_BEDTIME_SANITY_RANGE
    )
    assert resolved.sleep_component_relief == (
        provisional.L_THEANINE_BEDTIME_SLEEP_COMPONENT_RELIEF
    )
    item = next(item for item in load_protocol_items(context) if item["id"] == ITEM)
    estimate = estimate_item(item, specs[ITEM], baseline, context)
    assert estimate["mortality_qaly"] == pytest.approx(0.0, abs=1e-9)
    assert estimate["general_qol_qaly"] == 0.0
    assert estimate["sleep_qol_qaly"] >= 0.0
    assert estimate["qol_evidence"]["general_qol"] is None
    assert estimate["modeled_total_cost"] == round(
        modeled_total_cost(60.0, provisional.L_THEANINE_BEDTIME_QOL_YEARS), 2
    )
    assert estimate["within_range"]


def test_added_after_the_range_freeze_explicitly():
    assert ITEM in ITEMS_ADDED_AFTER_RANGE_FREEZE
    assert ITEM not in load_predeclared_ranges()["ranges"]
    drift = predeclared_range_drift(
        [
            {
                "id": ITEM,
                "range_low_qaly": -0.01,
                "range_high_qaly": 0.03,
                "total_qaly": 0,
            }
        ]
    )
    assert drift["items_added_after_freeze"] == [ITEM]
    assert drift["items_missing_from_freeze"] == []
    undeclared = predeclared_range_drift(
        [
            {
                "id": "not_frozen",
                "range_low_qaly": 0,
                "range_high_qaly": 0,
                "total_qaly": 0,
            }
        ]
    )
    assert undeclared["items_missing_from_freeze"] == ["not_frozen"]


def test_bedtime_theanine_is_searched_by_the_sleep_stack():
    items = [
        {"id": ITEM, "status": "taking", "time_of_day": "before_bed"},
        {"id": "l_theanine_200", "status": "taking", "time_of_day": None},
        {"id": "hyaluronic_acid_120", "status": "taking", "time_of_day": None},
    ]
    estimates = {item["id"]: {"name": CATALOG[item["id"]].name} for item in items}
    baseline = {
        "supplying_products": {
            ITEM: "L-Theanine 200mg",
            "hyaluronic_acid_120": "Blueprint Longevity Mix",
        }
    }
    universe, excluded = select_sleep_stack_universe(
        items, estimates, baseline=baseline
    )
    assert universe == [ITEM]
    assert excluded == []
