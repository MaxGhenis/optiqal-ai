"""Protocol integration for component overlap and exact legacy restoration."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from optiqal import protocol_ground_up as pgu
from optiqal.catalog import CATALOG
from optiqal.protocol_overlap import ProtocolInteractionEvaluator
from optiqal.sleep import (
    effective_sleep_component_relief,
    estimate_sleep_relief_annual_qaly,
)
from optiqal.sleep_overlap import SleepOverlapEvaluator
from optiqal.sleep_stack import SleepStackEvaluator, enumerate_feasible_subsets
from optiqal.stack_interactions import expected_stack_interaction_qaly

BASE_IDS = ["nac_1200"]
UNIVERSE_IDS = [
    "trazodone_50mg",
    "doxepin_3mg",
    "magnesium_200",
    "melatonin_300mcg",
    "glycine_2g",
    "ashwagandha_600",
    "apigenin_50",
]


@pytest.fixture
def real_estimates(monkeypatch):
    # These tests exercise guarded relief, mortality splitting, and stack
    # algebra; 512 paired draws suffice without repeating the 40k-draw suite.
    monkeypatch.setattr(pgu, "N_SIMULATIONS", 512)
    context = replace(pgu.resolve_protocol_context(None), residual_mode="authored")
    baseline = pgu.load_baseline(context)
    specs = pgu.build_specs(baseline, context)
    specs.update(pgu.build_additional_specs(baseline, context))
    # Exercise fractional windows through the complete estimate -> state path.
    specs["melatonin_300mcg"] = replace(specs["melatonin_300mcg"], qol_years=3.25)
    specs["glycine_2g"] = replace(specs["glycine_2g"], qol_years=8.75)
    loaded = {item["id"]: item for item in pgu.load_protocol_items(context)}
    estimates = {
        item_id: pgu.estimate_item(
            loaded[item_id], specs[item_id], baseline, context, include_draws=True
        )
        for item_id in BASE_IDS + UNIVERSE_IDS
    }
    return estimates, specs, context, baseline


def test_full_precision_relief_reproduces_each_standalone_sleep_qol(real_estimates):
    estimates, specs, context, baseline = real_estimates
    sleep = pgu.protocol_sleep_estimate_from_baseline_dict(baseline)
    for item_id, row in estimates.items():
        spec = pgu.resolve_stack_spec(specs[item_id], CATALOG[item_id])
        relief = pgu.guarded_component_relief(
            effective_sleep_component_relief(
                sleep, spec.sleep_component_relief, spec.airway_target_weights
            ),
            pgu.sleep_relief_evidence_for(item_id),
        )
        expected = estimate_sleep_relief_annual_qaly(
            sleep, relief
        ) * pgu.discount_factor(spec.qol_years)
        payload = row["sleep_overlap"]
        assert payload["relief"] == relief
        assert sum(payload["component_qol_qaly"].values()) == pytest.approx(
            expected, abs=1e-15
        )
        penalty, details = SleepOverlapEvaluator({item_id: row}).evaluate([item_id])
        assert penalty == 0.0
        assert details[0]["state_sleep_qol_qaly"] == pytest.approx(expected, abs=1e-15)
        state = pgu.evaluate_protocol_state([item_id], estimates, specs, context)
        assert state["_total_qaly_raw"] == pytest.approx(
            float(np.mean(row["_total_draws"])), abs=1e-12
        )


def _pre_b2_catalog():
    """Restore only B2's benefit-tag edits; B1 is a separate sensitivity."""
    entries = dict(CATALOG)
    for item_id, added in {
        "ashwagandha_600": {"anti_inflammatory"},
        "apigenin_50": {"anti_inflammatory", "senolytic_support"},
    }.items():
        entries[item_id] = replace(
            entries[item_id],
            benefit_tags=sorted(set(entries[item_id].benefit_tags) | added),
        )
    entries["nac_1200"] = replace(
        entries["nac_1200"],
        benefit_tags=[
            tag
            for tag in entries["nac_1200"].benefit_tags
            if tag != "sleep_quality_support"
        ],
    )
    return entries


def test_legacy_mode_matches_original_rank_retention_to_1e9(real_estimates):
    estimates, specs, context, _ = real_estimates
    assert context.residual_mode == "authored"
    years = pgu._state_item_active_years(list(estimates), specs)
    evaluator = ProtocolInteractionEvaluator(
        estimates,
        years,
        context.profile,
        pgu.QALY_DISCOUNT_RATE,
        "legacy_rank_retention",
    )
    assert "anti_inflammatory" in evaluator.catalog["ashwagandha_600"].benefit_tags
    assert "senolytic_support" in evaluator.catalog["apigenin_50"].benefit_tags
    assert "sleep_quality_support" not in evaluator.catalog["nac_1200"].benefit_tags
    for subset in enumerate_feasible_subsets(UNIVERSE_IDS)[::7]:
        ids = BASE_IDS + [UNIVERSE_IDS[index] for index in subset]
        expected, _ = expected_stack_interaction_qaly(
            item_ids=ids,
            catalog_entries=_pre_b2_catalog(),
            profile=context.profile,
            qaly_discount_rate=pgu.QALY_DISCOUNT_RATE,
            item_active_years=years,
            item_qalys=pgu._state_item_qalys(ids, estimates),
        )
        actual, _ = evaluator.evaluate(ids)
        assert abs(actual - expected) <= 1e-9


def test_legacy_restores_pre_b2_latent_ordering_without_reusing_component_cache(
    real_estimates,
):
    estimates, specs, context, _ = real_estimates
    ids = ["ashwagandha_600", "apigenin_50", "nac_1200"]
    component_draws = {
        item_id: pgu.latent_protocol_item_draws(item_id, estimates[item_id]).copy()
        for item_id in ids
    }
    historical = _pre_b2_catalog()
    expected_draws = {
        item_id: pgu.rank_preserving_latent_draws(
            estimates[item_id]["_total_draws"],
            pgu.latent_protocol_item_score(item_id, historical[item_id]),
        )
        for item_id in ids
    }
    interaction, _ = expected_stack_interaction_qaly(
        item_ids=ids,
        catalog_entries=historical,
        profile=context.profile,
        qaly_discount_rate=pgu.QALY_DISCOUNT_RATE,
        item_active_years=pgu._state_item_active_years(ids, specs),
        item_qalys=pgu._state_item_qalys(ids, estimates),
    )
    state = pgu.evaluate_protocol_state(
        ids, estimates, specs, replace(context, overlap_mode="legacy_rank_retention")
    )
    np.testing.assert_allclose(
        state["_draws"], sum(expected_draws.values()) + interaction, atol=1e-9, rtol=0
    )
    assert any(
        not np.array_equal(expected_draws[item_id], component_draws[item_id])
        for item_id in ids
    )
    for item_id in ids:
        np.testing.assert_array_equal(
            estimates[item_id]["_legacy_latent_total_draws"], expected_draws[item_id]
        )
        np.testing.assert_array_equal(
            pgu.latent_protocol_item_draws(item_id, estimates[item_id]),
            component_draws[item_id],
        )

    # S9 can restore an old sedation tag after S3 has already populated the
    # legacy cache. Reusing the same estimate must honor that changed tag set.
    item_id = "apigenin_50"
    sedating = replace(historical[item_id], interaction_tags=["sedating"])
    expected_sedating = pgu.rank_preserving_latent_draws(
        estimates[item_id]["_total_draws"],
        pgu.latent_protocol_item_score(item_id, sedating),
    )
    changed = pgu.latent_protocol_item_draws(
        item_id, estimates[item_id], legacy_entry=sedating
    )
    np.testing.assert_array_equal(changed, expected_sedating)
    assert not np.array_equal(changed, expected_draws[item_id])
    np.testing.assert_array_equal(
        pgu.latent_protocol_item_draws(
            item_id, estimates[item_id], legacy_entry=historical[item_id]
        ),
        expected_draws[item_id],
    )
    np.testing.assert_array_equal(
        pgu.latent_protocol_item_draws(item_id, estimates[item_id]),
        component_draws[item_id],
    )


def test_legacy_latent_only_synthetic_rows_keep_their_supplied_draws():
    draws = np.array([0.01, -0.02, 0.03])
    estimate = {"_latent_total_draws": draws}
    assert (
        pgu.latent_protocol_item_draws(
            "apigenin_50", estimate, legacy_entry=_pre_b2_catalog()["apigenin_50"]
        )
        is draws
    )


@pytest.mark.parametrize("mode", ["component", "legacy_rank_retention"])
def test_exhaustive_fast_path_matches_protocol_states_in_both_modes(
    real_estimates, mode
):
    estimates, specs, context, _ = real_estimates
    context = replace(context, overlap_mode=mode)
    evaluator = SleepStackEvaluator(BASE_IDS, UNIVERSE_IDS, estimates, specs, context)
    for subset in enumerate_feasible_subsets(UNIVERSE_IDS):
        state = pgu.evaluate_protocol_state(
            evaluator.state_ids(subset), estimates, specs, context
        )
        assert abs(evaluator.mean_qaly(subset) - state["_total_qaly_raw"]) <= 1e-9
        assert (
            abs(evaluator.total_cost(subset) - state["_modeled_total_cost_raw"]) <= 1e-9
        )
        np.testing.assert_allclose(
            evaluator.state_draws(subset), state["_draws"], atol=1e-9, rtol=0
        )


@pytest.mark.parametrize("mode", ["component", "legacy_rank_retention"])
def test_serialized_estimates_reproduce_full_precision_overlap(real_estimates, mode):
    estimates, specs, context, _ = real_estimates
    ids = list(estimates)
    years = pgu._state_item_active_years(ids, specs)
    public = {
        item_id: pgu.public_estimate_payload(row) for item_id, row in estimates.items()
    }
    private_value = ProtocolInteractionEvaluator(
        estimates, years, context.profile, pgu.QALY_DISCOUNT_RATE, mode
    ).evaluate(ids)[0]
    public_value = ProtocolInteractionEvaluator(
        public, years, context.profile, pgu.QALY_DISCOUNT_RATE, mode
    ).evaluate(ids)[0]
    assert abs(private_value - public_value) <= 1e-12


@pytest.mark.parametrize(
    "extra_tag, expected_nonsleep", [(None, -0.03), ("antioxidant_support", -0.06)]
)
def test_non_sleep_retention_only_penalizes_non_sleep_and_only_largest_tag(
    monkeypatch, extra_tag, expected_nonsleep
):
    ids = ["magnesium_200", "nac_1200"]
    tags = ["cardiometabolic_support", "sleep_quality_support"]
    if extra_tag is not None:
        tags.append(extra_tag)
    for item_id in ids:
        monkeypatch.setitem(
            CATALOG,
            item_id,
            replace(
                CATALOG[item_id],
                benefit_tags=tags,
                interaction_tags=[],
                interaction_rules=[],
            ),
        )
    years = 2.0
    discount = pgu.discount_factor(years)
    estimates = {}
    for item_id, relief, nonsleep in zip(ids, [0.3, 0.4], [0.2, 0.1]):
        estimates[item_id] = {
            "legacy_benefit_qaly": 100.0,
            "non_sleep_benefit_qaly": nonsleep,
            "sleep_overlap": {
                "relief": {"quality": relief},
                "annual_losses": {"quality": 0.02},
                "qol_years": years,
                "component_qol_qaly": {"quality": 0.02 * relief * discount},
            },
        }
    value, details = ProtocolInteractionEvaluator(
        estimates,
        dict.fromkeys(ids, years),
        pgu.PROFILE,
        pgu.QALY_DISCOUNT_RATE,
        "component",
    ).evaluate(ids)
    overlap = [row for row in details if row["id"].startswith("benefit_overlap:")]
    assert sum(row["penalty_qaly"] for row in overlap) == pytest.approx(
        expected_nonsleep, abs=1e-12
    )
    assert all("sleep_" not in row["id"] for row in overlap)
    assert value == pytest.approx(
        expected_nonsleep - 0.02 * 0.3 * 0.4 * discount, abs=1e-12
    )
