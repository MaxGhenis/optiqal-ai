"""Component overlap invariants, fractional horizons, and mortality bounds."""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from optiqal.profile import Profile
from optiqal.sleep_overlap import (
    SleepOverlapEvaluator,
    _mortality_arrays,
    mortality_approximation_bound,
    mortality_exposure_weights,
    sleep_component_overlap,
)


def estimate(relief, *, years=2.0, losses=None, mortality=0.0, kernel=None):
    losses = losses or {"quality": 0.02, "duration": 0.01}
    whole = int(years)
    discount = sum(1.03**-year for year in range(whole))
    discount += (years - whole) * 1.03**-whole
    return {
        "sleep_overlap": {
            "relief": relief,
            "annual_losses": losses,
            "qol_years": years,
            "component_qol_qaly": {
                component: fraction * losses[component] * discount
                for component, fraction in relief.items()
            },
            "sleep_mortality_qaly": mortality,
            "mortality_weights": {"quality": 1.0, "duration": 0.0},
            "mortality_year_weights": kernel or [1.0, 3.0, 2.0],
        }
    }


@pytest.mark.parametrize("years", [0.25, 1.0, 1.25, 8.0, 10.0, 12.5, 15.0])
def test_single_item_reproduces_its_standalone_component_qol(years):
    row = estimate({"quality": 0.2, "duration": 0.4}, years=years)
    penalty, details = sleep_component_overlap(["one"], {"one": row})
    assert penalty == 0.0
    assert details[0]["state_sleep_qol_qaly"] == pytest.approx(
        sum(row["sleep_overlap"]["component_qol_qaly"].values()), abs=1e-15
    )


def test_disjoint_components_have_no_interaction():
    rows = {
        "quality": estimate({"quality": 0.3}),
        "duration": estimate({"duration": 0.8}),
    }
    assert sleep_component_overlap(list(rows), rows)[0] == 0.0


def test_identical_components_compose_multiplicatively():
    row = estimate({"quality": 0.2})
    penalty, details = sleep_component_overlap(["a", "b"], {"a": row, "b": row})
    expected = 0.02 * (1 + 1 / 1.03) * (1 - (1 - 0.2) ** 2)
    assert details[0]["state_sleep_qol_qaly"] == pytest.approx(expected, abs=1e-15)
    assert penalty == pytest.approx(-0.02 * (1 + 1 / 1.03) * 0.2**2)


def test_fractional_horizons_compose_only_during_actual_shared_window():
    rows = {
        "short": estimate({"quality": 0.2}, years=1.25),
        "long": estimate({"quality": 0.4}, years=1.75),
    }
    penalty, details = sleep_component_overlap(list(rows), rows)
    # Both are active through year 1.25; only the second from 1.25 to 1.75.
    expected = 0.02 * ((1 + 0.25 / 1.03) * (1 - 0.8 * 0.6) + 0.5 / 1.03 * 0.4)
    assert details[0]["state_sleep_qol_qaly"] == pytest.approx(expected, abs=1e-15)
    assert penalty == pytest.approx(-0.02 * 0.2 * 0.4 * (1 + 0.25 / 1.03))


def test_sleep_interaction_is_nonpositive_for_all_random_subsets():
    rng = np.random.default_rng(7107)
    rows = {
        str(i): estimate(
            {"quality": float(rng.uniform()), "duration": float(rng.uniform())},
            years=float(rng.uniform(0.01, 15)),
        )
        for i in range(7)
    }
    evaluator = SleepOverlapEvaluator(rows)
    for n in range(len(rows) + 1):
        for ids in itertools.combinations(rows, n):
            value, details = evaluator.evaluate(ids)
            assert value <= 0.0
            assert value == evaluator.interaction_qaly(ids)
            if details:
                assert details[0]["state_sleep_qol_qaly"] >= -1e-15


def test_mortality_uses_overlap_windows_and_lifetime_kernel():
    rows = {
        "short": estimate({"quality": 0.2}, years=1, mortality=0.1),
        "long": estimate({"quality": 0.2}, years=2, mortality=0.2),
    }
    _, details = sleep_component_overlap(list(rows), rows)
    # Combined .36 versus summed .4 removes 10% during year 0. The longer
    # item's year-0 share of its lifetime mortality exposure is 1/(1+3).
    assert details[0]["sleep_mortality_interaction_qaly"] == pytest.approx(
        -0.1 * (0.1 + 0.2 / 4), abs=1e-15
    )
    assert (
        sleep_component_overlap(["short"], rows)[1][0]["state_sleep_mortality_qaly"]
        == 0.1
    )


def test_rejects_inconsistent_standalone_or_baseline_inputs():
    row = estimate({"quality": 0.2})
    row["sleep_overlap"]["component_qol_qaly"]["quality"] *= 2
    with pytest.raises(ValueError, match="does not match"):
        SleepOverlapEvaluator({"a": row})
    with pytest.raises(ValueError, match="different baseline"):
        SleepOverlapEvaluator(
            {
                "a": estimate({"quality": 0.2}),
                "b": estimate({"quality": 0.2}, losses={"quality": 0.05}),
            }
        )


def test_empty_or_missing_sleep_payload_has_zero_interaction():
    assert sleep_component_overlap([], {}) == (0.0, [])
    assert sleep_component_overlap(["not_sleep"], {"not_sleep": {}}) == (0.0, [])


PROFILE = Profile(
    age=35,
    sex="male",
    bmi_category="normal",
    smoking_status="never",
    has_diabetes=False,
)


def test_mortality_kernel_includes_survival_after_active_year():
    baseline = 1.02
    kernel = mortality_exposure_weights(PROFILE, baseline)
    qx, quality_discount, survival = _mortality_arrays(PROFILE, baseline, 0.03)
    perturbation = 1e-6
    changed_qx = qx.copy()
    changed_qx[0] *= np.exp(-perturbation)
    changed_survival = np.concatenate(([1.0], np.cumprod(1 - changed_qx)))[:-1]
    finite_difference = (
        np.sum((changed_survival - survival) * quality_discount) / perturbation
    )
    assert kernel[0] == pytest.approx(finite_difference, rel=1e-5)
    assert kernel[0] > qx[0] * quality_discount[1]
    assert kernel[-1] == 0.0


def test_proportional_mortality_bound_covers_each_subset():
    baseline = 1.03
    kernel = mortality_exposure_weights(PROFILE, baseline)
    qx, quality_discount, survival = _mortality_arrays(PROFILE, baseline, 0.03)
    rows = {}
    for i, (fraction, years) in enumerate([(0.1, 2), (0.2, 8), (0.3, 10)]):
        changed_qx = qx.copy()
        changed_qx[:years] *= baseline**-fraction
        changed_survival = np.concatenate(([1.0], np.cumprod(1 - changed_qx)))[:-1]
        mortality = float(np.sum((changed_survival - survival) * quality_discount))
        rows[str(i)] = estimate(
            {"quality": fraction}, years=years, mortality=mortality, kernel=kernel
        )
    bound = mortality_approximation_bound(rows, PROFILE, baseline)
    for n in range(1, len(rows) + 1):
        for ids in itertools.combinations(rows, n):
            selected = {item_id: rows[item_id] for item_id in ids}
            actual = mortality_approximation_bound(selected, PROFILE, baseline)
            assert (
                actual["all_items_absolute_error_qaly"]
                <= bound["all_subsets_absolute_error_bound_qaly"]
            )
    assert bound["all_subsets_absolute_error_bound_qaly"] < 0.001
