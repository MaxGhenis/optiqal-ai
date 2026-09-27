"""The Eight Sleep Pod 6 upgrade item and its provisional parameters.

Invariants checked here:
- cost round-trip: the annualized cost, run through the engine's own
  modeled_total_cost, reproduces the one-time price (differential against the
  engine's discount_factor, and the rate matches QALY_DISCOUNT_RATE);
- the expected breathing relief is exactly P(available) x relief if available
  x share of device life (rounded to 4 dp), and every fraction is in [0, 1];
- the sleep-QoL leg is zero at zero relief and nondecreasing in each relief
  fraction (exhaustive grid through estimate_item);
- the item is a sleep-stack candidate with no general-QoL leg, and no
  mortality leg at Max's REI.
"""

from __future__ import annotations

import dataclasses
import itertools

import pytest

from optiqal import provisional_params as provisional
from optiqal.catalog import CATALOG
from optiqal.confounding import CATEGORY_PRIORS
from optiqal.protocol_ground_up import (
    COST_DISCOUNT_RATE,
    ITEMS_ADDED_AFTER_RANGE_FREEZE,
    build_additional_specs,
    build_specs,
    discount_factor,
    estimate_item,
    load_baseline,
    load_predeclared_ranges,
    load_protocol_items,
    modeled_total_cost,
    resolve_protocol_context,
    resolve_stack_spec,
)
from optiqal.qol_annotations import general_qol_evidence_for, sleep_relief_evidence_for
from optiqal.sleep import SLEEP_COMPONENT_BENEFIT_TAGS
from optiqal.sleep_stack import select_sleep_stack_universe

ITEM = "eight_sleep_pod6_upgrade"


def test_catalog_entry_reads_the_provisional_parameters():
    assert provisional.EIGHT_SLEEP_POD6_UPGRADE_ID == ITEM
    entry = CATALOG[ITEM]
    assert entry.name == "Eight Sleep Pod 6 upgrade"
    assert entry.category == "sleep_candidate"
    assert entry.bundle_id is None
    assert entry.hr_observed == provisional.EIGHT_SLEEP_POD6_HR == 1.0
    assert entry.has_direct_mortality_effect is False
    assert entry.qol_annual == provisional.EIGHT_SLEEP_POD6_QOL_ANNUAL == 0.0
    assert entry.qol_years == provisional.EIGHT_SLEEP_POD6_QOL_YEARS
    assert dict(entry.sleep_component_relief) == (
        provisional.EIGHT_SLEEP_POD6_SLEEP_COMPONENT_RELIEF
    )
    assert dict(entry.airway_target_weights) == (
        provisional.EIGHT_SLEEP_POD6_AIRWAY_TARGET_WEIGHTS
    )
    assert entry.benefit_tags == [
        SLEEP_COMPONENT_BENEFIT_TAGS[component]
        for component in provisional.EIGHT_SLEEP_POD6_SLEEP_COMPONENT_RELIEF
    ]
    # Not a sedative and not an exclusive OSA therapy: it composes with APAP.
    assert entry.interaction_tags == []
    assert entry.exclusive_group is None


def test_prior_is_the_category_fallback_not_a_new_judgment():
    entry = CATALOG[ITEM]
    fallback = CATEGORY_PRIORS["other"]
    assert (entry.conf_alpha, entry.conf_beta) == (fallback.alpha, fallback.beta)


def test_one_time_price_round_trips_through_the_engine_cost():
    assert provisional._POD6_DISCOUNT_RATE == COST_DISCOUNT_RATE
    years = provisional.EIGHT_SLEEP_POD6_QOL_YEARS
    assert years == int(years)
    annual = provisional.EIGHT_SLEEP_POD6_ANNUAL_COST
    assert annual * discount_factor(years) == pytest.approx(
        provisional.EIGHT_SLEEP_POD6_ONE_TIME_PRICE_USD, abs=1e-9
    )
    assert modeled_total_cost(CATALOG[ITEM].annual_cost, years) == pytest.approx(
        provisional.EIGHT_SLEEP_POD6_ONE_TIME_PRICE_USD, abs=1e-9
    )


@pytest.mark.parametrize("price", [0.0, 1.0, 999.0, 2999.0, 12345.67])
@pytest.mark.parametrize("years", [1, 2, 5, 7, 10])
def test_annualization_round_trips_for_any_price_and_life(price, years):
    rate = provisional._POD6_DISCOUNT_RATE
    annual = price / sum((1.0 + rate) ** -t for t in range(years))
    assert modeled_total_cost(annual, float(years)) == pytest.approx(price, abs=1e-9)


def test_expected_breathing_relief_is_the_stated_product():
    relief = provisional.EIGHT_SLEEP_POD6_SLEEP_COMPONENT_RELIEF
    assert relief["breathing"] == round(
        provisional.POD6_P_APNEA_MITIGATION_AVAILABLE
        * provisional.POD6_BREATHING_RELIEF_IF_AVAILABLE
        * provisional.POD6_SHARE_OF_LIFE_AVAILABLE,
        4,
    )
    assert relief["quality"] == provisional.POD6_THERMAL_QUALITY_RELIEF
    for probability in (
        provisional.POD6_P_APNEA_MITIGATION_AVAILABLE,
        provisional.POD6_SHARE_OF_LIFE_AVAILABLE,
    ):
        assert 0.0 <= probability <= 1.0
    assert all(0.0 <= fraction <= 1.0 for fraction in relief.values())


def test_qol_guard_annotation_uses_the_provisional_tier():
    assert general_qol_evidence_for(ITEM) is None  # no general-QoL claim
    evidence = sleep_relief_evidence_for(ITEM)
    assert evidence is not None
    assert evidence.study_quality == provisional.EIGHT_SLEEP_POD6_QOL_STUDY_QUALITY
    assert evidence.category == provisional.EIGHT_SLEEP_POD6_QOL_CATEGORY
    assert evidence.anchor == "published_delta"
    head = sleep_relief_evidence_for("head_elevation_nightly")
    assert (evidence.study_quality, evidence.category) == (
        head.study_quality,
        head.category,
    )


@pytest.fixture(scope="module")
def engine_inputs():
    context = resolve_protocol_context(None)
    baseline = load_baseline(context)
    specs = build_specs(baseline, context)
    specs.update(build_additional_specs(baseline, context))
    item = next(item for item in load_protocol_items(context) if item["id"] == ITEM)
    return context, baseline, specs, item


def test_spec_is_sparse_and_the_estimate_is_sleep_only(engine_inputs):
    context, baseline, specs, item = engine_inputs
    resolved = resolve_stack_spec(specs[ITEM], CATALOG[ITEM])
    assert (resolved.low_qaly, resolved.high_qaly) == (
        provisional.EIGHT_SLEEP_POD6_SANITY_RANGE
    )
    assert resolved.qol_years == provisional.EIGHT_SLEEP_POD6_QOL_YEARS
    estimate = estimate_item(item, specs[ITEM], baseline, context)
    # Max's REI (~8) gates breathing out of the sleep mortality signal and the
    # item relieves no other mortality-weighted component: no mortality leg.
    assert estimate["mortality_qaly"] == pytest.approx(0.0, abs=1e-9)
    assert estimate["general_qol_qaly"] == 0.0
    assert estimate["direct_harm_qaly"] == 0.0
    assert estimate["sleep_qol_qaly"] >= 0.0
    assert estimate["modeled_total_cost"] == pytest.approx(
        provisional.EIGHT_SLEEP_POD6_ONE_TIME_PRICE_USD, abs=0.01
    )
    assert estimate["within_range"]


_GRID = (0.0, 0.01, 0.05, 0.2)


def test_sleep_qol_is_zero_at_zero_relief_and_monotone(engine_inputs):
    context, baseline, specs, item = engine_inputs
    values = {}
    for breathing, quality in itertools.product(_GRID, _GRID):
        spec = dataclasses.replace(
            specs[ITEM],
            sleep_component_relief={"breathing": breathing, "quality": quality},
        )
        estimate = estimate_item(item, spec, baseline, context)
        values[(breathing, quality)] = estimate["sleep_qol_qaly"]
    assert values[(0.0, 0.0)] == 0.0
    for (b, q), value in values.items():
        for (b2, q2), other in values.items():
            if b2 >= b and q2 >= q:
                assert other >= value - 1e-12, ((b, q), (b2, q2))


def test_added_after_the_range_freeze_explicitly():
    assert ITEM in ITEMS_ADDED_AFTER_RANGE_FREEZE
    assert ITEM not in load_predeclared_ranges()["ranges"]


def test_upgrade_is_searched_by_the_sleep_stack():
    items = [{"id": ITEM, "status": "considering", "time_of_day": None}]
    estimates = {ITEM: {"name": CATALOG[ITEM].name}}
    universe, excluded = select_sleep_stack_universe(items, estimates, baseline={})
    assert universe == [ITEM]
    assert excluded == []
