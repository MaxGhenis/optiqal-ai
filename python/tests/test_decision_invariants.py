"""Invariants of decision analysis, catalog simulation and portfolio optimizers.

Each test names the invariant it enforces:

- DROP = -ADD: dropping an item is the exact negation of adding it on the same
  draws, for items with harms, QoL-only items and mortality items alike.
- Harms preserved: a decision carries the catalog's harm model and interaction
  rules, so an ADD without overrides reproduces the item's catalog row.
- Same quantity: the point estimate, P(benefit), P(harm), the 95% and 80%
  intervals and the expected upside and downside summarize one set of
  total-QALY draws.
- Exclusivity: no optimizer, and no ``analyze()`` result, holds two members of
  one mutually exclusive group.
- Hash-seed determinism: outputs do not depend on ``PYTHONHASHSEED``.
- Catalog-subset invariance: an entry's row does not depend on which other
  entries are simulated with it, or in what order.

The regression tests start from the minimized counterexamples of the
2026-09-25 invariants audit and assert the correct values. Where a test needs
a value independent of the code under test, it recomputes it here from raw
data (the draws themselves, or a closed form for additive portfolios).
"""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import optiqal.analyzer as analyzer_module
import optiqal.catalog as catalog_module
from optiqal.analyzer import AnalysisConfig, Decision, analyze, evaluate_decisions
from optiqal.catalog import CATALOG, get_catalog, simulate_catalog
from optiqal.combination import (
    find_optimal_portfolio,
    find_optimal_portfolio_from_qalys,
    find_optimal_portfolio_with_costs,
    rank_interventions_by_marginal_cost_per_qaly,
)
from optiqal.confounding import publication_bias_correct
from optiqal.intervention import Distribution, Intervention, MortalityEffect
from optiqal.profile import Profile
from optiqal.report import format_decision_table
from optiqal.sleep import SleepMetrics

DAYS_PER_QALY = 365.25
SHIPPED_IDS = sorted(CATALOG)
PYTHON_ROOT = Path(__file__).resolve().parents[1]

# Decision-row fields DROP negates: every QALY, day and money quantity.
NEGATED_FIELDS = (
    "mort_qaly",
    "harm_qaly",
    "direct_harm_qaly",
    "interaction_harm_qaly",
    "qol_qaly",
    "sleep_qol_annual",
    "sleep_qol_qaly",
    "total_qaly",
    "days",
    "annual_cost",
    "total_cost",
    "net_value",
)

# Decision-row field -> catalog-row field it must equal for an ADD without
# overrides (the same simulation, projected onto the decision keys).
DECISION_TO_CATALOG_FIELD = {
    "mort_qaly": "mort_qaly",
    "posterior_hr": "hr_posterior_mean",
    "harm_qaly": "harm_qaly",
    "direct_harm_qaly": "direct_harm_qaly",
    "interaction_harm_qaly": "interaction_harm_qaly",
    "qol_qaly": "qol_qaly",
    "qol_years": "qol_years",
    "sleep_qol_annual": "sleep_qol_annual",
    "sleep_qol_qaly": "sleep_qol_qaly",
    "total_qaly": "total_qaly",
    "days": "days",
    "annual_cost": "effective_annual_cost",
    "total_cost": "total_cost",
    "cost_per_qaly": "cost_per_qaly",
    "net_value": "gross_value",
    "p_benefit": "p_benefit",
    "p_harm": "p_harm",
    "expected_upside_days": "expected_upside_days",
    "expected_downside_days": "expected_downside_days",
    "ci_low": "ci_low",
    "ci_high": "ci_high",
    "net_qaly_ci": "net_qaly_ci",
}

SLEEP_METRICS = SleepMetrics(
    duration_hours=6.4,
    recovery_score=52.0,
    sleep_quality_score=76.0,
    waso_min=18.0,
    routine_score=68.0,
    social_jetlag_min=55.0,
    latency_min=23.0,
    breathing_score=0.75,
    spo2=95.0,
    snore_pct=4.0,
    sleep_debt_min=70.0,
)


def _profile(age: int = 40, sex: str = "male") -> Profile:
    return Profile(age, sex, "normal", "never", False)


def _config(
    age: int = 40,
    sex: str = "male",
    n_simulations: int = 100,
    random_state: int = 42,
    sleep: bool = False,
) -> AnalysisConfig:
    return AnalysisConfig(
        profile=_profile(age, sex),
        n_simulations=n_simulations,
        random_state=random_state,
        sleep_metrics=SLEEP_METRICS if sleep else None,
    )


def _expected_verdict(net_value: float) -> str:
    if net_value > 0:
        return "DO IT"
    return "MARGINAL" if net_value > -2000 else "SKIP"


def _percentile(sorted_values: list, q: float) -> float:
    """Linear-interpolation percentile (numpy's default method), from scratch."""
    position = (len(sorted_values) - 1) * q / 100
    lower = math.floor(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (
        fraction
    )


def _summaries_from_draws(draws) -> dict:
    """What every decision summary must be, recomputed from the draws alone."""
    values = sorted(float(value) for value in draws)
    n = len(values)
    mean = math.fsum(values) / n
    return {
        "total_qaly": mean,
        "days": mean * DAYS_PER_QALY,
        "p_benefit": sum(value > 0 for value in values) / n,
        "p_harm": sum(value < 0 for value in values) / n,
        "ci_low": _percentile(values, 2.5) * DAYS_PER_QALY,
        "ci_high": _percentile(values, 97.5) * DAYS_PER_QALY,
        "net_qaly_ci": [_percentile(values, 10), _percentile(values, 90)],
        "expected_upside_days": math.fsum(max(v, 0.0) for v in values)
        / n
        * DAYS_PER_QALY,
        "expected_downside_days": math.fsum(min(v, 0.0) for v in values)
        / n
        * DAYS_PER_QALY,
    }


def _assert_row_summarizes_draws(row: dict, draws) -> None:
    expected = _summaries_from_draws(draws)
    for key in ("p_benefit", "p_harm"):
        assert row[key] == expected[key], key
    for key in (
        "total_qaly",
        "days",
        "ci_low",
        "ci_high",
        "expected_upside_days",
        "expected_downside_days",
    ):
        assert row[key] == pytest.approx(expected[key], rel=1e-9, abs=1e-12), key
    assert row["net_qaly_ci"] == pytest.approx(
        expected["net_qaly_ci"], rel=1e-9, abs=1e-12
    )


def _assert_drop_negates_add(add: dict, drop: dict) -> None:
    for key in NEGATED_FIELDS:
        assert drop[key] == -add[key], key
    assert drop["p_benefit"] == add["p_harm"]
    assert drop["p_harm"] == add["p_benefit"]
    assert drop["ci_low"] == -add["ci_high"]
    assert drop["ci_high"] == -add["ci_low"]
    assert drop["net_qaly_ci"] == [-add["net_qaly_ci"][1], -add["net_qaly_ci"][0]]
    assert drop["expected_upside_days"] == -add["expected_downside_days"]
    assert drop["expected_downside_days"] == -add["expected_upside_days"]
    # These describe the item rather than the change.
    assert drop["posterior_hr"] == add["posterior_hr"]
    assert drop["qol_years"] == add["qol_years"]
    assert drop["cost_per_qaly"] is None
    assert drop["verdict"] == _expected_verdict(drop["net_value"])


def _evaluate_with_draws(decision: Decision, config: AnalysisConfig):
    return analyzer_module._evaluate_decision(decision, config)


# ---------------------------------------------------------------------------
# DROP = -ADD
# ---------------------------------------------------------------------------


def test_drop_is_negated_add_for_vitamin_d_regression():
    """DROP = -ADD. Audit: vitamin_d_2000, 40-year-old man, 100 draws, seed 42.

    Both ADD and DROP returned +0.06423917056625499 QALYs and "DO IT", because
    DROP kept the item's hazard ratio.
    """
    rows = evaluate_decisions(
        [
            Decision(action, "vitamin_d_2000", "same label")
            for action in ("add", "drop")
        ],
        _config(),
    )
    by_type = {row["decision_type"]: row for row in rows}
    add, drop = by_type["add"], by_type["drop"]

    assert add["total_qaly"] > 0
    assert add["net_value"] > 0
    assert drop["total_qaly"] == -add["total_qaly"] < 0
    assert drop["mort_qaly"] == -add["mort_qaly"] < 0
    assert drop["verdict"] != "DO IT"
    _assert_drop_negates_add(add, drop)


@pytest.mark.parametrize("age", [18, 40, 85])
@pytest.mark.parametrize("sex", ["male", "female"])
@pytest.mark.parametrize(
    "item_id",
    [
        "vitamin_d_2000",  # mortality item
        "creatine_5g",  # mortality, componentized QoL draws and a harm
        "glycine_2g",  # QoL-only
        "trazodone_50mg",  # QoL-only with an annual harm
        "aspirin_81mg",  # mortality with an event harm
    ],
)
def test_drop_is_negated_add_grid(age, sex, item_id):
    """DROP = -ADD over the audit's age/sex grid, extended to harmful items."""
    config = _config(age, sex, n_simulations=32)
    add, add_draws = _evaluate_with_draws(Decision("add", item_id, "x"), config)
    drop, drop_draws = _evaluate_with_draws(Decision("drop", item_id, "x"), config)

    _assert_drop_negates_add(add, drop)
    np.testing.assert_array_equal(drop_draws, -add_draws)


@settings(max_examples=40, deadline=None, derandomize=True, database=None)
@given(
    item_id=st.sampled_from(SHIPPED_IDS),
    age=st.integers(18, 99),
    sex=st.sampled_from(["male", "female"]),
    n_simulations=st.integers(8, 32),
    random_state=st.integers(0, 2**31 - 1),
    sleep=st.booleans(),
    override_hr=st.none() | st.just(1.0) | st.floats(0.5, 1.5),
    override_cost=st.none() | st.floats(0, 2000),
    override_qol=st.none() | st.floats(-0.01, 0.01),
)
def test_drop_is_negated_add_property(
    item_id,
    age,
    sex,
    n_simulations,
    random_state,
    sleep,
    override_hr,
    override_cost,
    override_qol,
):
    """DROP = -ADD for every shipped item, profile, seed and override set.

    Both rows also summarize their own draws, and the DROP draws are the ADD
    draws negated, so each identity is checked against the draws as well.
    """
    config = _config(age, sex, n_simulations, random_state, sleep)
    overrides = {
        "override_hr": override_hr,
        "override_cost": override_cost,
        "override_qol": override_qol,
    }
    add, add_draws = _evaluate_with_draws(
        Decision("add", item_id, "x", **overrides), config
    )
    drop, drop_draws = _evaluate_with_draws(
        Decision("drop", item_id, "x", **overrides), config
    )

    _assert_drop_negates_add(add, drop)
    np.testing.assert_array_equal(drop_draws, -add_draws)
    _assert_row_summarizes_draws(add, add_draws)
    _assert_row_summarizes_draws(drop, drop_draws)


# ---------------------------------------------------------------------------
# Harms preserved from catalog to decision
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("item_id", ["trazodone_50mg", "doxepin_3mg"])
def test_add_keeps_shipped_harms_regression(item_id):
    """Harms preserved. Audit: 40-year-old man, 100 draws, seed 42.

    ADD rebuilt the intervention with only its mortality arm, so trazodone's
    direct harm (-0.0260 QALYs in the catalog) became 0 and its total flipped
    from -0.0197 to +0.0063; doxepin flipped the same way.
    """
    config = _config()
    catalog_row = simulate_catalog(
        config.profile,
        n_simulations=100,
        random_state=42,
        catalog_entries={item_id: CATALOG[item_id]},
    )[0]
    decision = evaluate_decisions([Decision("add", item_id, item_id)], config)[0]

    assert catalog_row["direct_harm_qaly"] < 0
    assert decision["direct_harm_qaly"] == catalog_row["direct_harm_qaly"]
    assert decision["harm_qaly"] == catalog_row["harm_qaly"]
    assert decision["total_qaly"] == catalog_row["total_qaly"]
    assert decision["net_value"] == catalog_row["gross_value"]


@pytest.mark.parametrize("age,sex", [(40, "male"), (70, "female")])
def test_add_without_overrides_reproduces_every_catalog_row(age, sex):
    """Harms preserved: an unmodified ADD equals the catalog row, every item.

    Every numeric decision field equals its catalog counterpart, so harms,
    interaction rules, QoL draws, bundle cost allocation and uncertainty all
    carry over. Items declaring an annual harm must show a strictly negative
    direct harm.
    """
    config = _config(age, sex, n_simulations=16, random_state=7)
    catalog_rows = {
        row["id"]: row
        for row in simulate_catalog(config.profile, n_simulations=16, random_state=7)
    }
    decisions = evaluate_decisions(
        [Decision("add", item_id, item_id) for item_id in SHIPPED_IDS], config
    )

    assert sorted(row["item_id"] for row in decisions) == SHIPPED_IDS
    for decision in decisions:
        catalog_row = catalog_rows[decision["item_id"]]
        for decision_field, catalog_field in DECISION_TO_CATALOG_FIELD.items():
            expected = catalog_row[catalog_field]
            if decision_field == "posterior_hr" and expected is None:
                expected = 1.0
            if decision_field == "net_qaly_ci":
                expected = list(expected)
            assert decision[decision_field] == expected, (
                decision["item_id"],
                decision_field,
            )
        entry = CATALOG[decision["item_id"]]
        if any(harm.annual_qaly_loss is not None for harm in entry.harm_effects):
            assert decision["direct_harm_qaly"] < 0, decision["item_id"]


@pytest.mark.parametrize("item_id", SHIPPED_IDS)
def test_decision_intervention_carries_catalog_harm_model(item_id):
    """Harms preserved structurally, with and without an HR override.

    An HR override replaces only the hazard-ratio mean (publication-bias
    corrected) and keeps the entry's log SD and confounding prior.
    """
    entry = CATALOG[item_id]
    config = _config()
    catalog_intervention = entry.to_intervention(
        config.pub_bias_shrinkage, profile=config.profile
    )
    for decision in (
        Decision("add", item_id, "x"),
        Decision("add", item_id, "x", override_hr=0.8),
    ):
        intervention = analyzer_module._decision_intervention(entry, decision, config)
        assert intervention.harm_model == catalog_intervention.harm_model
        assert intervention.interaction_tags == catalog_intervention.interaction_tags
        assert intervention.interaction_rules == catalog_intervention.interaction_rules

    overridden = analyzer_module._decision_intervention(
        entry, Decision("add", item_id, "x", override_hr=0.8), config
    )
    params = overridden.mortality.hazard_ratio.params
    assert params["hr"] == publication_bias_correct(0.8, config.pub_bias_shrinkage)
    assert params["log_sd"] == entry.log_sd
    assert overridden.confounding_prior.alpha == entry.conf_alpha
    assert overridden.confounding_prior.beta == entry.conf_beta


# ---------------------------------------------------------------------------
# Intervals and probabilities describe the same quantity as the point estimate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "age,sex,action",
    [(40, "male", "add"), (18, "female", "add"), (85, "male", "drop")],
)
def test_qol_only_uncertainty_describes_total_qalys_regression(age, sex, action):
    """Same quantity. Audit: glycine_2g, 100 draws, seed 42.

    ADD reported +0.00157 QALYs with P(benefit) 0 and a 95% CI of [0, 0]
    days, and an age-85 DROP was strictly negative with P(harm) 0, because the
    probabilities and the 95% interval came from the mortality draws alone.
    Since #27 the shared bedtime evidence rule zeroes glycine's duplicate sleep
    residual, so this uses probiotic_daily, another QoL-only item without harms
    whose QoL draws are all positive, to exercise the same path.
    """
    row = evaluate_decisions(
        [Decision(action, "probiotic_daily", "Probiotic")], _config(age, sex)
    )[0]
    if action == "add":
        assert row["total_qaly"] > 0
        assert row["p_benefit"] == 1.0
        assert row["p_harm"] == 0.0
        assert 0 < row["ci_low"] <= row["days"] <= row["ci_high"]
        assert 0 < row["net_qaly_ci"][0] <= row["total_qaly"] <= row["net_qaly_ci"][1]
        assert row["expected_downside_days"] == 0.0
    else:
        assert row["total_qaly"] < 0
        assert row["p_harm"] == 1.0
        assert row["p_benefit"] == 0.0
        assert row["ci_low"] <= row["days"] <= row["ci_high"] < 0
        assert row["net_qaly_ci"][0] <= row["total_qaly"] <= row["net_qaly_ci"][1] < 0
        assert row["expected_upside_days"] == 0.0


def _qol_only_items_without_harms() -> list:
    return [
        item_id
        for item_id, entry in sorted(CATALOG.items())
        if not entry.has_direct_mortality_effect and not entry.harm_effects
    ]


@settings(max_examples=30, deadline=None, derandomize=True, database=None)
@given(
    item_id=st.sampled_from(_qol_only_items_without_harms()),
    action=st.sampled_from(["add", "drop", "adjust"]),
    age=st.integers(18, 95),
    annual_qol=st.floats(1e-4, 0.05) | st.floats(-0.05, -1e-4),
    n_simulations=st.integers(4, 64),
)
def test_deterministic_total_collapses_every_interval(
    item_id, action, age, annual_qol, n_simulations
):
    """Same quantity: a deterministic total has no spread and a sure sign.

    A QoL-only item without harms, given a fixed annual QoL, has the same
    total in every draw, so both intervals collapse onto the point estimate
    and the probability of that sign is exactly one.
    """
    row, draws = _evaluate_with_draws(
        Decision(action, item_id, "x", override_qol=annual_qol),
        _config(age, n_simulations=n_simulations),
    )
    assert np.all(draws == draws[0])
    point = row["total_qaly"]
    assert point == pytest.approx(float(draws[0]), rel=1e-12)
    assert row["ci_low"] == row["ci_high"] == pytest.approx(row["days"], rel=1e-12)
    assert row["net_qaly_ci"][0] == row["net_qaly_ci"][1]
    assert row["net_qaly_ci"][0] == pytest.approx(point, rel=1e-12)
    if point > 0:
        assert (row["p_benefit"], row["p_harm"]) == (1.0, 0.0)
    else:
        assert (row["p_benefit"], row["p_harm"]) == (0.0, 1.0)


@settings(max_examples=40, deadline=None, derandomize=True, database=None)
@given(
    item_id=st.sampled_from(SHIPPED_IDS),
    action=st.sampled_from(["add", "drop", "adjust"]),
    age=st.integers(18, 99),
    sex=st.sampled_from(["male", "female"]),
    n_simulations=st.integers(4, 64),
    random_state=st.integers(0, 2**31 - 1),
    sleep=st.booleans(),
    override_qol=st.none() | st.floats(-0.01, 0.01),
)
def test_decision_summaries_describe_total_qaly_draws(
    item_id, action, age, sex, n_simulations, random_state, sleep, override_qol
):
    """Same quantity: every summary is of the total-QALY draws, and the
    mortality, harm, QoL and sleep QoL components add up to the total."""
    row, draws = _evaluate_with_draws(
        Decision(action, item_id, "x", override_qol=override_qol),
        _config(age, sex, n_simulations, random_state, sleep),
    )
    assert len(draws) == n_simulations
    _assert_row_summarizes_draws(row, draws)
    components = (
        row["mort_qaly"] + row["harm_qaly"] + row["qol_qaly"] + row["sleep_qol_qaly"]
    )
    assert row["total_qaly"] == pytest.approx(components, rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("item_id", SHIPPED_IDS)
def test_shipped_intervals_contain_the_point_estimate(item_id):
    """Same quantity, data check: each shipped item's 95% and 80% intervals
    contain its expected total, for decisions in both directions.

    hbot_60sessions used to fail here: its event harm was sampled as a whole
    event per draw, so the rare event skewed the draws and the mean fell
    outside the 80% interval. Draws now carry the expected event loss.
    """
    for age, sex in ((40, "male"), (85, "female")):
        config = _config(age, sex, n_simulations=64)
        for action in ("add", "drop"):
            row = evaluate_decisions([Decision(action, item_id, "x")], config)[0]
            assert row["ci_low"] <= row["days"] <= row["ci_high"], (age, sex, action)
            low, high = row["net_qaly_ci"]
            assert low <= row["total_qaly"] <= high, (age, sex, action)


def test_decision_table_labels_the_interval_as_total_days():
    """The report says what the interval describes."""
    rows = evaluate_decisions(
        [Decision("add", "probiotic_daily", "ADD: Probiotic")], _config()
    )
    table = format_decision_table(rows)
    assert "95% CI, days" in table
    assert "change in total quality-adjusted days" in table


# ---------------------------------------------------------------------------
# Exclusivity respected end to end
# ---------------------------------------------------------------------------

SHIPPED_EXCLUSIVE_PAIRS = [
    ("hiit_1x_week", "hiit_2x_week"),
    ("zone2_cardio_2x_week", "tempo_run_1x_week"),
]


@pytest.mark.parametrize("pair", SHIPPED_EXCLUSIVE_PAIRS)
@pytest.mark.parametrize("stack", ["empty", "first_member"])
def test_analyze_selects_one_member_of_a_shipped_exclusive_pair_regression(pair, stack):
    """Exclusivity. Audit: normal 40-year-old man, 100 draws, seed 42.

    analyze() selected both HIIT schedules (total 0.02506 QALYs) and both
    zone 2 and tempo runs, because its optimizer took no exclusive groups.
    Both optimizers must now keep one member: the better one from an empty
    stack, the current one otherwise.
    """
    entries = {item_id: CATALOG[item_id] for item_id in pair}
    assert entries[pair[0]].exclusive_group == entries[pair[1]].exclusive_group
    current_stack = [] if stack == "empty" else [pair[0]]
    result = analyze(_config(), current_stack=current_stack, catalog_entries=entries)
    rows = result.item_results_by_id

    if stack == "empty":
        best = max(pair, key=lambda item_id: (rows[item_id]["gross_value"], item_id))
        assert rows[best]["gross_value"] > 0
        assert result.selected_ids == [best]
    else:
        assert result.selected_ids == [pair[0]]

    ranking = rank_interventions_by_marginal_cost_per_qaly(
        single_qalys={item_id: rows[item_id]["total_qaly"] for item_id in pair},
        annual_costs={
            item_id: rows[item_id]["effective_annual_cost"] for item_id in pair
        },
        cost_values={item_id: rows[item_id]["total_cost"] for item_id in pair},
        preselected=current_stack,
        exclusive_groups={
            item_id: entries[item_id].exclusive_group for item_id in pair
        },
    )
    selected = ranking[-1]["selected_interventions"] if ranking else current_stack
    assert len(selected) == 1


@pytest.mark.parametrize(
    "current_stack", [[], ["hiit_1x_week", "apap_nightly", "trazodone_50mg"]]
)
def test_analyze_full_catalog_respects_every_exclusive_group(current_stack):
    """Exclusivity over the whole shipped catalog, empty and occupied stacks."""
    result = analyze(
        _config(n_simulations=16, random_state=5), current_stack=current_stack
    )
    groups = [
        CATALOG[item_id].exclusive_group
        for item_id in result.selected_ids
        if CATALOG[item_id].exclusive_group
    ]
    assert len(groups) == len(set(groups))
    assert result.selected_ids[: len(current_stack)] == current_stack


def _point_intervention(item_id: str) -> Intervention:
    return Intervention(
        id=item_id,
        name=item_id,
        category="exercise",
        mortality=MortalityEffect(
            hazard_ratio=Distribution(type="point", params={"value": 0.9})
        ),
    )


def _walk(order: list, preselected: list, groups: dict, stop) -> list:
    """Closed-form greedy result for an additive portfolio.

    With additive QALYs and costs, every candidate's marginal score is fixed,
    so the greedy path visits candidates in one static order, stops at the
    first nonpositive score, and skips any whose group is already held.
    """
    taken = {groups[item_id] for item_id in preselected if item_id in groups}
    added = []
    for item_id in order:
        if stop(item_id):
            break
        group = groups.get(item_id)
        if group is not None and group in taken:
            continue
        added.append(item_id)
        if group is not None:
            taken.add(group)
    return added


@st.composite
def additive_portfolios(draw):
    """Additive portfolios with exactly representable arithmetic.

    QALYs are multiples of 1/8 and costs whole dollars, so every sum and
    difference the optimizers take is exact and ties are real ties.
    """
    n_items = draw(st.integers(1, 7))
    ids = [f"i{index}" for index in range(n_items)]
    qalys = {item_id: draw(st.integers(-8, 24)) / 8 for item_id in ids}
    costs = {item_id: float(draw(st.integers(0, 60))) for item_id in ids}
    groups = {}
    for item_id in ids:
        group = draw(st.sampled_from([None, "g0", "g1", "g2"]))
        if group is not None:
            groups[item_id] = group
    preselected = []
    held = set()
    for item_id in ids:
        if draw(st.booleans()) and draw(st.booleans()):
            if groups.get(item_id) in held:
                continue
            preselected.append(item_id)
            if item_id in groups:
                held.add(groups[item_id])
    wtp = draw(st.sampled_from([1, 8, 64, 200]))
    return ids, qalys, costs, groups, preselected, wtp


def _assert_one_per_group(selected: list, groups: dict) -> None:
    held = [groups[item_id] for item_id in selected if item_id in groups]
    assert len(held) == len(set(held)), selected


@settings(max_examples=150, deadline=None, derandomize=True, database=None)
@given(portfolio=additive_portfolios())
def test_every_optimizer_matches_closed_form_with_exclusive_groups(portfolio):
    """Exclusivity and the sorted-id tie-break, against a closed form.

    For additive inputs each optimizer's path is fixed in advance (see
    ``_walk``), so the exact selection, including which member of a group
    wins and how exact ties break, is known without running the optimizer.
    """
    ids, qalys, costs, groups, preselected, wtp = portfolio
    available = [item_id for item_id in ids if item_id not in preselected]

    # Cost-aware greedy: highest net value first, first id on exact ties.
    net = {item_id: qalys[item_id] * wtp - costs[item_id] for item_id in ids}
    path = find_optimal_portfolio_with_costs(
        qalys,
        {item_id: 0.0 for item_id in ids},
        cost_values=costs,
        wtp=wtp,
        preselected=preselected,
        exclusive_groups=groups,
    )
    expected = _walk(
        sorted(available, key=lambda i: (-net[i], i)),
        preselected,
        groups,
        stop=lambda i: net[i] <= 0,
    )
    assert [step["added_intervention"] for step in path] == expected
    for step in path:
        _assert_one_per_group(step["selected_interventions"], groups)
        assert step["selected_interventions"][: len(preselected)] == preselected

    # Cost-effectiveness ranker: lowest cost per QALY, then larger QALY, then id.
    def ratio(item_id):
        return costs[item_id] / qalys[item_id] if costs[item_id] > 0 else 0.0

    positive = [item_id for item_id in available if qalys[item_id] > 0]
    ranking = rank_interventions_by_marginal_cost_per_qaly(
        qalys,
        {item_id: 0.0 for item_id in ids},
        cost_values=costs,
        preselected=preselected,
        exclusive_groups=groups,
    )
    expected = _walk(
        sorted(positive, key=lambda i: (ratio(i), -qalys[i], i)),
        preselected,
        groups,
        stop=lambda i: False,
    )
    assert [step["added_intervention"] for step in ranking] == expected
    for step in ranking:
        _assert_one_per_group(step["selected_interventions"], groups)

    # QALY-only optimizers (no preselection): highest QALY first.
    expected = _walk(
        sorted(ids, key=lambda i: (-qalys[i], i)),
        [],
        groups,
        stop=lambda i: qalys[i] <= 0,
    )
    from_qalys = find_optimal_portfolio_from_qalys(
        qalys, max_interventions=len(ids), exclusive_groups=groups
    )
    assert [step["added_intervention"] for step in from_qalys] == expected
    with_objects = find_optimal_portfolio(
        [_point_intervention(item_id) for item_id in ids],
        _profile(),
        max_interventions=len(ids),
        precomputed_qalys=qalys,
        exclusive_groups=groups,
    )
    assert [selected[-1] for selected, _ in with_objects] == expected


@settings(max_examples=60, deadline=None, derandomize=True, database=None)
@given(
    portfolio=additive_portfolios(),
    penalties=st.dictionaries(
        st.tuples(st.integers(0, 6), st.integers(0, 6)),
        st.integers(-16, 8).map(lambda value: value / 8),
        max_size=6,
    ),
    ceiling=st.none() | st.sampled_from([0.5, 2.0]),
)
def test_optimizers_hold_one_member_per_group_under_interactions(
    portfolio, penalties, ceiling
):
    """Exclusivity with pairwise interaction penalties and saturation."""
    ids, qalys, costs, groups, preselected, wtp = portfolio

    def penalty_fn(item_ids):
        held = set(item_ids)
        return sum(
            value
            for (a, b), value in penalties.items()
            if a != b and f"i{a}" in held and f"i{b}" in held
        )

    common = {
        "cost_values": costs,
        "preselected": preselected,
        "stack_interaction_penalty_fn": penalty_fn,
        "exclusive_groups": groups,
    }
    zero_costs = {item_id: 0.0 for item_id in ids}
    for path in (
        find_optimal_portfolio_with_costs(
            qalys, zero_costs, wtp=wtp, portfolio_qaly_ceiling=ceiling, **common
        ),
        rank_interventions_by_marginal_cost_per_qaly(qalys, zero_costs, **common),
    ):
        for step in path:
            _assert_one_per_group(step["selected_interventions"], groups)


# ---------------------------------------------------------------------------
# Determinism independent of PYTHONHASHSEED
# ---------------------------------------------------------------------------

_HASH_SEED_PROBE = """
import json

from optiqal.analyzer import AnalysisConfig, Decision, analyze
from optiqal.catalog import CATALOG
from optiqal.combination import (
    find_optimal_portfolio_from_qalys,
    find_optimal_portfolio_with_costs,
    rank_interventions_by_marginal_cost_per_qaly,
)
from optiqal.profile import Profile


def ids(path):
    return [step["added_intervention"] for step in path]


def penalty(item_ids):
    return -2.0 if {"a", "c"} <= set(item_ids) else 0.0


tie = {"a": 1.0, "b": 1.0}
zero = {"a": 0.0, "b": 0.0, "c": 0.0}
three = {"a": 1.0, "b": 1.0, "c": 0.5}
groups = {"a": "g", "b": "g"}
out = {
    "tie_ranker": ids(rank_interventions_by_marginal_cost_per_qaly(tie, zero)),
    "tie_costs": ids(find_optimal_portfolio_with_costs(tie, zero, wtp=10.0)),
    "tie_from_qalys": ids(find_optimal_portfolio_from_qalys(tie)),
}
ranker = rank_interventions_by_marginal_cost_per_qaly(
    three, zero, exclusive_groups=groups, stack_interaction_penalty_fn=penalty
)
out["exclusive_ranker"] = [ids(ranker), ranker[-1]["total_qaly"]]
costs = find_optimal_portfolio_with_costs(
    three,
    zero,
    wtp=10.0,
    exclusive_groups=groups,
    stack_interaction_penalty_fn=penalty,
)
out["exclusive_costs"] = [ids(costs), costs[-1]["total_qaly"]]

subset = [
    "creatine_5g",
    "glycine_2g",
    "hiit_1x_week",
    "hiit_2x_week",
    "trazodone_50mg",
    "doxepin_3mg",
    "vitamin_d_2000",
]
result = analyze(
    AnalysisConfig(
        profile=Profile(40, "male", "normal", "never", False),
        n_simulations=32,
        random_state=42,
    ),
    catalog_entries={item_id: CATALOG[item_id] for item_id in subset},
    decisions=[
        Decision("add", "creatine_5g", "add creatine"),
        Decision("drop", "trazodone_50mg", "drop trazodone"),
    ],
)
out["analyze"] = {
    "selected": result.selected_ids,
    "total_qaly": result.total_qaly,
    "rows": [[row["id"], row["total_qaly"]] for row in result.item_results],
    "decisions": [[row["label"], row["total_qaly"]] for row in result.decisions],
}
print(json.dumps(out, sort_keys=True))
"""


def test_outputs_do_not_depend_on_python_hash_seed():
    """Determinism: identical outputs under six PYTHONHASHSEED values.

    Audit: {a: 1, b: 1} at zero cost ranked as ['a', 'b'] or ['b', 'a'] by
    hash seed; with a and b exclusive and a -2 penalty when a and c coexist,
    the ranker's final total was 1.0 or 1.5. The documented tie-break (first
    id in sorted order) makes both deterministic.
    """
    env = {
        **os.environ,
        "OPENBLAS_NUM_THREADS": "1",
        "PYTHONPATH": os.pathsep.join(
            [str(PYTHON_ROOT), os.environ.get("PYTHONPATH", "")]
        ),
    }
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", _HASH_SEED_PROBE],
            cwd=PYTHON_ROOT,
            env={**env, "PYTHONHASHSEED": str(seed)},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for seed in range(6)
    ]
    outputs = []
    for process in processes:
        stdout, stderr = process.communicate(timeout=300)
        assert process.returncode == 0, stderr
        outputs.append(stdout.strip())

    assert len(set(outputs)) == 1, sorted(set(outputs))
    probe = json.loads(outputs[0])
    assert probe["tie_ranker"] == ["a", "b"]
    assert probe["tie_costs"] == ["a", "b"]
    assert probe["tie_from_qalys"] == ["a", "b"]
    # 'a' wins the a/b tie; c then loses 1.5 QALYs to the penalty and stops.
    assert probe["exclusive_ranker"] == [["a"], 1.0]
    assert probe["exclusive_costs"] == [["a"], 1.0]
    selected_groups = [
        CATALOG[item_id].exclusive_group
        for item_id in probe["analyze"]["selected"]
        if CATALOG[item_id].exclusive_group
    ]
    assert len(selected_groups) == len(set(selected_groups))


# ---------------------------------------------------------------------------
# Catalog-subset invariance
# ---------------------------------------------------------------------------

SUBSET_POOL = (
    "creatine_5g",
    "vitamin_d_2000",
    "glycine_2g",
    "trazodone_50mg",
    "hbot_60sessions",
    "hiit_2x_week",
    "aspirin_81mg",
)


def _row_alone(item_id: str, **kwargs) -> dict:
    return simulate_catalog(catalog_entries={item_id: CATALOG[item_id]}, **kwargs)[0]


def test_creatine_row_ignores_the_rest_of_the_catalog_regression():
    """Catalog-subset invariance. creatine_5g's QoL draws were seeded by its
    position among the simulated entries, so its row changed with the
    category filter and with whatever else was simulated."""
    kwargs = {"profile": _profile(), "n_simulations": 100, "random_state": 42}
    alone = _row_alone("creatine_5g", **kwargs)
    full = {row["id"]: row for row in simulate_catalog(**kwargs)}["creatine_5g"]
    category = CATALOG["creatine_5g"].category
    filtered = {
        row["id"]: row for row in simulate_catalog(categories=[category], **kwargs)
    }["creatine_5g"]
    assert len(get_catalog([category])) < len(CATALOG)
    assert full == alone
    assert filtered == alone


@settings(max_examples=12, deadline=None, derandomize=True, database=None)
@given(
    ordered=st.permutations(SUBSET_POOL),
    size=st.integers(1, len(SUBSET_POOL)),
    random_state=st.integers(0, 2**31 - 1),
    age=st.integers(18, 90),
)
def test_catalog_rows_are_invariant_to_subset_and_order(
    ordered, size, random_state, age
):
    """Catalog-subset invariance: each row equals the row simulated alone,
    and the rows' order depends only on which entries were simulated."""
    kwargs = {
        "profile": _profile(age),
        "n_simulations": 16,
        "random_state": random_state,
    }
    subset = list(ordered[:size])
    rows = simulate_catalog(
        catalog_entries={item_id: CATALOG[item_id] for item_id in subset}, **kwargs
    )
    alone = {item_id: _row_alone(item_id, **kwargs) for item_id in subset}

    assert [row["id"] for row in rows] == sorted(
        subset, key=lambda item_id: (-alone[item_id]["gross_value"], item_id)
    )
    for row in rows:
        assert row == alone[row["id"]]


def test_catalog_entry_helper_returns_the_draws_behind_the_row():
    """Same quantity at the source: the helper's draws are the row's draws."""
    row, draws = catalog_module.simulate_catalog_entry(
        CATALOG["creatine_5g"], _profile(), n_simulations=64, random_state=3
    )
    assert row == _row_alone(
        "creatine_5g", profile=_profile(), n_simulations=64, random_state=3
    )
    _assert_row_summarizes_draws(row, draws)
