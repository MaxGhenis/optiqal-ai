"""Tests for the exhaustive sleep-stack search."""

from __future__ import annotations

import itertools
import json
import math

import numpy as np
import pytest

import optiqal.protocol_ground_up as protocol_ground_up
from optiqal.catalog import CATALOG
from optiqal.protocol_ground_up import (
    build_additional_specs,
    build_specs,
    estimate_item,
    evaluate_protocol_state,
    load_baseline,
    load_protocol_items,
    make_spec,
    resolve_protocol_context,
)
from optiqal.sleep_stack import (
    SleepStackEvaluator,
    enumerate_feasible_subsets,
    expected_state_count,
    optimize_sleep_stack,
    render_sleep_stack_markdown,
    select_sleep_stack_universe,
    sleep_domain_reasons,
)

# A synthetic universe over real catalog ids, so exclusive groups come from the
# catalog: three insomnia prescriptions, both primary OSA therapies, and three
# ungrouped sleep items. prod(|group| + 1) * 2**ungrouped = 4 * 3 * 8 = 96.
SYNTHETIC_GROUPED = {
    "insomnia_rx": ["trazodone_50mg", "doxepin_3mg", "daridorexant_25mg"],
    "osa_primary_therapy": ["apap_nightly", "oral_appliance_custom"],
}
SYNTHETIC_UNGROUPED = ["magnesium_200", "melatonin_300mcg", "nasacort_nightly"]
SYNTHETIC_BASE = ["vitamin_d_2000", "omega3_clo"]
SYNTHETIC_CURRENT = {"trazodone_50mg", "magnesium_200", "melatonin_300mcg"}


def _fake_estimate(item_id: str, index: int, n: int) -> dict:
    rng = np.random.default_rng(1000 + index)
    draws = rng.normal(loc=0.002 * (index % 5) - 0.003, scale=0.004, size=n)
    return {
        "id": item_id,
        "name": CATALOG[item_id].name,
        "total_qaly": round(float(np.mean(draws)), 4),
        "modeled_total_cost": float(100 * (index + 1)),
        "_latent_total_draws": draws,
        "_benefit_overlap_qaly": max(float(np.mean(draws)), 0.0),
    }


@pytest.fixture
def synthetic_inputs():
    ids = (
        SYNTHETIC_BASE
        + [item_id for group in SYNTHETIC_GROUPED.values() for item_id in group]
        + SYNTHETIC_UNGROUPED
    )
    n = protocol_ground_up.N_SIMULATIONS
    estimates = {
        item_id: _fake_estimate(item_id, index, n) for index, item_id in enumerate(ids)
    }
    specs = {
        item_id: make_spec(item_id, low_qaly=-1.0, high_qaly=1.0) for item_id in ids
    }
    protocol_items = [
        {
            "id": item_id,
            "name": CATALOG[item_id].name,
            "status": (
                "taking"
                if item_id in SYNTHETIC_CURRENT or item_id in SYNTHETIC_BASE
                else "considering"
            ),
            "time_of_day": None,
        }
        for item_id in ids
    ]
    return protocol_items, estimates, specs, resolve_protocol_context(None)


def _small_result(synthetic_inputs, **kwargs):
    protocol_items, estimates, specs, context = synthetic_inputs
    return optimize_sleep_stack(
        protocol_items,
        estimates,
        specs,
        context,
        wtps=(50_000, 200_000),
        top_n=10,
        p_best_top_k=12,
        **kwargs,
    )


def test_state_count_is_product_of_group_options_times_ungrouped_powerset(
    synthetic_inputs,
):
    result = _small_result(synthetic_inputs)
    universe = [row["id"] for row in result["universe"]]

    grouped = math.prod(len(members) + 1 for members in SYNTHETIC_GROUPED.values())
    expected = grouped * 2 ** len(SYNTHETIC_UNGROUPED)
    assert expected == 96
    assert expected_state_count(universe) == expected
    assert result["state_count"] == expected
    assert result["expected_state_count"] == expected
    subsets = enumerate_feasible_subsets(universe)
    assert len(subsets) == len(set(subsets)) == expected
    assert result["exclusive_groups"] == SYNTHETIC_GROUPED
    assert result["n_ungrouped"] == len(SYNTHETIC_UNGROUPED)
    assert result["held_fixed_item_count"] == len(SYNTHETIC_BASE)


def test_enumeration_is_exactly_the_feasible_powerset(synthetic_inputs):
    result = _small_result(synthetic_inputs)
    universe = [row["id"] for row in result["universe"]]

    def feasible(subset):
        groups = [
            CATALOG[universe[index]].exclusive_group
            for index in subset
            if CATALOG[universe[index]].exclusive_group
        ]
        return len(groups) == len(set(groups))

    brute_force = {
        subset
        for size in range(len(universe) + 1)
        for subset in itertools.combinations(range(len(universe)), size)
        if feasible(subset)
    }
    assert set(enumerate_feasible_subsets(universe)) == brute_force

    group_of = {
        item_id: group
        for group, members in SYNTHETIC_GROUPED.items()
        for item_id in members
    }
    reported_states = [result["qaly"]["optimum"]] + result["qaly"]["top"]
    for block in result["net_benefit"].values():
        reported_states += [block["optimum"], *block["top"]]
    for state in reported_states:
        groups = [
            group_of[item_id] for item_id in state["item_ids"] if item_id in group_of
        ]
        assert len(groups) == len(set(groups)), state["item_ids"]


def test_optimum_beats_or_ties_every_single_flip_neighbour(synthetic_inputs):
    protocol_items, estimates, specs, context = synthetic_inputs
    result = _small_result(synthetic_inputs)
    universe = [row["id"] for row in result["universe"]]
    base = [item_id for item_id in SYNTHETIC_BASE]
    evaluator = SleepStackEvaluator(base, universe, estimates, specs, context)

    def value(ids, wtp):
        subset = tuple(sorted(universe.index(item_id) for item_id in ids))
        qaly = evaluator.mean_qaly(subset)
        return qaly if wtp is None else qaly * wtp - evaluator.total_cost(subset)

    blocks = [(None, result["qaly"])] + [
        (float(wtp), block) for wtp, block in result["net_benefit"].items()
    ]
    for wtp, block in blocks:
        optimum = set(block["optimum"]["item_ids"])
        best = value(optimum, wtp)
        for item_id in universe:
            neighbour = set(optimum)
            if item_id in neighbour:
                neighbour.discard(item_id)
            else:
                group = CATALOG[item_id].exclusive_group
                neighbour = {
                    other
                    for other in neighbour
                    if not group or CATALOG[other].exclusive_group != group
                }
                neighbour.add(item_id)
            assert best >= value(neighbour, wtp) - 1e-12, (wtp, item_id)
        # The reported single-flip rows carry the same sign convention.
        for row in block["single_flip_neighbours"]:
            key = "marginal_qaly" if wtp is None else "marginal_net_benefit"
            if row["in_optimum"]:
                assert row[key] >= 0
            else:
                assert row[key] <= 0


def test_optimum_is_the_best_state_by_brute_force(synthetic_inputs):
    protocol_items, estimates, specs, context = synthetic_inputs
    result = _small_result(synthetic_inputs)
    universe = [row["id"] for row in result["universe"]]
    evaluator = SleepStackEvaluator(SYNTHETIC_BASE, universe, estimates, specs, context)
    values = {
        subset: (evaluator.mean_qaly(subset), evaluator.total_cost(subset))
        for subset in enumerate_feasible_subsets(universe)
    }
    for wtp, block in result["net_benefit"].items():
        best = max(values.values(), key=lambda qc: qc[0] * float(wtp) - qc[1])
        assert block["optimum"]["objective_value"] == pytest.approx(
            best[0] * float(wtp) - best[1], abs=0.01
        )
    best_qaly = max(qaly for qaly, _ in values.values())
    assert result["qaly"]["optimum"]["state_qaly"] == pytest.approx(best_qaly, abs=1e-5)


def test_output_is_deterministic(synthetic_inputs):
    first = _small_result(synthetic_inputs)
    second = _small_result(synthetic_inputs)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_current_state_and_deltas_are_paired(synthetic_inputs):
    result = _small_result(synthetic_inputs)
    current = result["current_state"]
    assert set(current["item_ids"]) == SYNTHETIC_CURRENT
    assert current["feasible"] is True
    for block in result["net_benefit"].values():
        delta = block["delta_vs_current"]
        assert delta["delta_ci80"][0] <= delta["delta_qaly"] <= delta["delta_ci80"][1]
        assert 0.0 <= delta["p_delta_positive"] <= 1.0
        assert block["optimum"]["delta_net_benefit"] >= 0
        assert block["current_rank"] >= 1
        assert 0.0 < block["p_best"]["optimum_p_best"] <= 1.0
        shares = sum(row["p_best"] for row in block["p_best"]["states"])
        assert shares == pytest.approx(1.0, abs=1e-3)


def test_cost_overrides_move_costs_but_not_qaly(synthetic_inputs):
    cash = _small_result(synthetic_inputs)
    free = _small_result(
        synthetic_inputs,
        cost_overrides={"trazodone_50mg": 0.0, "apap_nightly": 0.0},
    )
    assert cash["perspective"] == "cash"
    assert free["perspective"] == "custom_costs"
    assert free["cost_overrides"] == {"apap_nightly": 0.0, "trazodone_50mg": 0.0}
    costs = {row["id"]: row["modeled_total_cost"] for row in free["universe"]}
    assert costs["trazodone_50mg"] == 0.0
    assert costs["apap_nightly"] == 0.0
    assert free["qaly"]["optimum"] == cash["qaly"]["optimum"] | {
        "state_cost": free["qaly"]["optimum"]["state_cost"],
        "delta_cost": free["qaly"]["optimum"]["delta_cost"],
    }
    with pytest.raises(ValueError, match="unknown items"):
        _small_result(synthetic_inputs, cost_overrides={"not_an_item": 1.0})


def test_default_universe_rules():
    items = [
        {"id": "trazodone_50mg", "status": "taking"},
        {"id": "doxepin_3mg", "status": "considering"},
        # Sleep-domain only through its schedule.
        {"id": "taurine_500_topup", "status": "testing", "time_of_day": "bedtime"},
        # Morning item without sleep relief: not sleep-domain.
        {"id": "vitamin_d_2000", "status": "taking", "time_of_day": "meal_1"},
        # Sleep relief, but shipped in one capsule with two other tracked items.
        {"id": "nac_1200", "status": "taking"},
        {"id": "curcumin_250", "status": "taking"},
        {"id": "ginger_400", "status": "taking"},
        # Not current and not actionable: never searched.
        {"id": "apigenin_50", "status": "stopped"},
    ]
    estimates = {item["id"]: {"name": CATALOG[item["id"]].name} for item in items}
    baseline = {
        "supplying_products": {
            "nac_1200": "Blueprint NAC+Ginger+Curcumin",
            "curcumin_250": "Blueprint NAC+Ginger+Curcumin",
            "ginger_400": "Blueprint NAC+Ginger+Curcumin",
            "taurine_500_topup": "Taurine 500mg",
        }
    }
    universe, excluded = select_sleep_stack_universe(
        items, estimates, baseline=baseline
    )

    assert universe == ["trazodone_50mg", "doxepin_3mg", "taurine_500_topup"]
    assert [row["id"] for row in excluded] == ["nac_1200"]
    assert "not separably droppable" in excluded[0]["reason"]
    assert "Blueprint NAC+Ginger+Curcumin" in excluded[0]["reason"]
    assert sleep_domain_reasons(items[2]) == ["time_of_day:bedtime"]
    assert sleep_domain_reasons(items[0]) == [
        "sleep_component_relief",
        "exclusive_group:insomnia_rx",
    ]
    assert sleep_domain_reasons(items[3]) == []


def test_held_fixed_item_blocks_its_exclusive_group():
    items = [
        {"id": "trazodone_50mg", "status": "taking"},
        {"id": "doxepin_3mg", "status": "considering"},
    ]
    estimates = {item["id"]: {"name": item["id"]} for item in items}
    # Trazodone ships in a (hypothetical) combination product, so it is held
    # fixed; doxepin would then break the one-per-group constraint.
    baseline = {"supplying_products": {"trazodone_50mg": "Combo", "doxepin_3mg": "X"}}
    items.append({"id": "melatonin_300mcg", "status": "taking"})
    baseline["supplying_products"]["melatonin_300mcg"] = "Combo"
    estimates["melatonin_300mcg"] = {"name": "melatonin"}
    universe, excluded = select_sleep_stack_universe(
        items, estimates, baseline=baseline
    )
    assert universe == []
    reasons = {row["id"]: row["reason"] for row in excluded}
    assert "occupied by held-fixed item trazodone_50mg" in reasons["doxepin_3mg"]


def test_explicit_universe_is_validated(synthetic_inputs):
    protocol_items, estimates, specs, context = synthetic_inputs
    result = _small_result(
        synthetic_inputs, universe_ids=["melatonin_300mcg", "trazodone_50mg"]
    )
    assert [row["id"] for row in result["universe"]] == [
        "trazodone_50mg",
        "melatonin_300mcg",
    ]
    assert result["state_count"] == 4
    left_out = {row["id"] for row in result["excluded"]}
    assert "magnesium_200" in left_out
    with pytest.raises(ValueError, match="not a protocol item"):
        _small_result(synthetic_inputs, universe_ids=["humidifier_nightly"])


def test_markdown_section_renders(synthetic_inputs):
    result = _small_result(synthetic_inputs)
    result["runtime_seconds"] = 1.5
    text = "\n".join(render_sleep_stack_markdown(result))
    assert text.startswith("## Sleep stack (exhaustive search)")
    assert "96 states" in text
    assert "$200,000/QALY" in text
    assert "QALY only" in text


# --------------------------------------------------------------------------
# Real pipeline estimates: the fast path must equal evaluate_protocol_state.
# --------------------------------------------------------------------------
REAL_BASE = ["vitamin_d_2000", "omega3_clo", "tadalafil_2.5mg", "nac_1200"]
REAL_UNIVERSE = [
    "trazodone_50mg",
    "doxepin_3mg",
    "lemborexant_5mg",
    "apap_nightly",
    "oral_appliance_custom",
    "nasacort_nightly",
    "nasal_strips_nightly",
    "head_elevation_nightly",
    "humidifier_nightly",
    "magnesium_200",
    "melatonin_300mcg",
    "glycine_2g",
    "ashwagandha_600",
    "apigenin_50",
]


@pytest.fixture(scope="module")
def real_inputs():
    baseline = load_baseline()
    specs = build_specs(baseline)
    specs.update(build_additional_specs(baseline))
    context = resolve_protocol_context(None)
    loaded = {item["id"]: item for item in load_protocol_items()}
    estimates = {
        item_id: estimate_item(
            loaded[item_id], specs[item_id], baseline, context, include_draws=True
        )
        for item_id in REAL_BASE + REAL_UNIVERSE
    }
    return estimates, specs, context


def test_fast_path_equals_evaluate_protocol_state(real_inputs):
    estimates, specs, context = real_inputs
    evaluator = SleepStackEvaluator(REAL_BASE, REAL_UNIVERSE, estimates, specs, context)
    subsets = enumerate_feasible_subsets(REAL_UNIVERSE)
    rng = np.random.default_rng(20260923)
    picks = [subsets[0], subsets[-1]] + [
        subsets[int(index)] for index in rng.choice(len(subsets), 22, replace=False)
    ]
    assert len(picks) >= 20
    for subset in picks:
        ids = evaluator.state_ids(subset)
        reference = evaluate_protocol_state(ids, estimates, specs, context)
        assert abs(evaluator.mean_qaly(subset) - reference["_total_qaly_raw"]) <= 1e-9
        assert (
            abs(evaluator.total_cost(subset) - reference["_modeled_total_cost_raw"])
            <= 1e-9
        )
        assert (
            float(np.max(np.abs(evaluator.state_draws(subset) - reference["_draws"])))
            <= 1e-9
        )


def test_fast_path_cost_overrides_equal_overridden_estimates(real_inputs):
    estimates, specs, context = real_inputs
    overrides = {"trazodone_50mg": 0.0, "apap_nightly": 12.5, "vitamin_d_2000": 3.0}
    evaluator = SleepStackEvaluator(
        REAL_BASE, REAL_UNIVERSE, estimates, specs, context, cost_overrides=overrides
    )
    overridden = {
        item_id: (
            estimate | {"modeled_total_cost": overrides[item_id]}
            if item_id in overrides
            else estimate
        )
        for item_id, estimate in estimates.items()
    }
    for subset in enumerate_feasible_subsets(REAL_UNIVERSE)[::997]:
        reference = evaluate_protocol_state(
            evaluator.state_ids(subset), overridden, specs, context
        )
        assert (
            abs(evaluator.total_cost(subset) - reference["_modeled_total_cost_raw"])
            <= 1e-9
        )
