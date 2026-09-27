"""Compose guarded sleep relief on the component and active-window scales.

QoL composition is exact, including fractional final years. Mortality overlap
uses the same component composition, with proportional allocation of each
item's standalone sleep-derived mortality QALY. Its exposure weights are the
life-table derivative with respect to a temporary log-hazard reduction, so
survival gains after treatment stops remain in the allocation. This is a
first-order mortality approximation; ``mortality_approximation_bound`` bounds
its error against an exact combined sleep-HR life-table calculation.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy.special import ndtr

from .defaults import DEFAULT_QALY_DISCOUNT_RATE, validate_qaly_discount_rate
from .lifecycle import QUALITY_WEIGHT_STD, get_mortality_rate, get_quality_weight
from .profile import Profile, get_baseline_mortality_multiplier


def _integral(weights: np.ndarray, years: float) -> float:
    """Integrate a piecewise-constant annual stream, prorating its final year."""
    years = max(0.0, min(float(years), len(weights)))
    whole = int(math.floor(years))
    value = float(np.sum(weights[:whole]))
    if whole < len(weights):
        value += (years - whole) * float(weights[whole])
    return value


def _mortality_arrays(
    profile: Profile, baseline_hazard_multiplier: float, discount_rate: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ages = np.arange(profile.age, 100)
    qx = np.minimum(
        np.array([get_mortality_rate(int(age), profile.sex) for age in ages])
        * get_baseline_mortality_multiplier(profile)
        * max(0.0, baseline_hazard_multiplier),
        0.99,
    )
    quality = np.array([get_quality_weight(int(age)) for age in ages])
    # Exact expectation of the simulator's clipped Normal quality weights.
    # Correlation of a person's offset across years does not affect the mean.
    lower = (0.1 - quality) / QUALITY_WEIGHT_STD
    upper = (1.0 - quality) / QUALITY_WEIGHT_STD

    def normal_density(value: np.ndarray) -> np.ndarray:
        return np.exp(-0.5 * value**2) / math.sqrt(2 * math.pi)

    mean_quality = (
        quality * (ndtr(upper) - ndtr(lower))
        + QUALITY_WEIGHT_STD * (normal_density(lower) - normal_density(upper))
        + 0.1 * ndtr(lower)
        + 1.0
        - ndtr(upper)
    )
    discount = (1.0 + discount_rate) ** -np.arange(len(ages), dtype=float)
    survival = np.concatenate(([1.0], np.cumprod(1.0 - qx)))[:-1]
    return qx, mean_quality * discount, survival


def mortality_exposure_weights(
    profile: Profile,
    baseline_hazard_multiplier: float,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
) -> list[float]:
    """Lifetime QALY derivative for log-hazard relief in each future year.

    A treatment's hazard effect ends at ``qol_years`` in the current simulator,
    but the people alive because of it continue accruing QALYs afterward.
    Thus these weights integrate downstream survival to age 100, rather than
    discounting mortality benefit only over the treatment window.
    """
    discount_rate = validate_qaly_discount_rate(discount_rate)
    qx, quality_discount, survival = _mortality_arrays(
        profile, baseline_hazard_multiplier, discount_rate
    )
    future_qaly = np.cumsum((survival * quality_discount)[::-1])[::-1]
    after_year = future_qaly - survival * quality_discount
    return (qx / (1.0 - qx) * after_year).tolist()


class SleepOverlapEvaluator:
    """Prepare reusable arrays for exact QoL and proportional mortality overlap.

    Inputs are estimate_item payloads. ``sleep_overlap`` (or its private alias
    ``_sleep_overlap``) carries full-precision ``relief``, ``annual_losses``,
    ``qol_years``, ``component_qol_qaly``, ``sleep_mortality_qaly``, normalized
    component ``mortality_weights``, and common ``mortality_year_weights``.
    Missing payloads represent items with no modeled sleep benefit.

    Preparation splits the timeline only at distinct treatment horizons.
    State evaluation is a few NumPy reductions, with no annual Python loop.
    """

    def __init__(
        self,
        estimates_by_id: Mapping[str, Mapping[str, Any]],
        discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    ) -> None:
        self.discount_rate = validate_qaly_discount_rate(discount_rate)
        self.payloads = {
            item_id: payload
            for item_id, estimate in estimates_by_id.items()
            if (
                payload := estimate.get("_sleep_overlap")
                or estimate.get("sleep_overlap")
            )
            and payload.get("relief")
            and float(payload.get("qol_years", 0.0)) > 0
        }
        self.item_ids = list(self.payloads)
        self.index = {item_id: i for i, item_id in enumerate(self.item_ids)}
        self.components = sorted(
            {
                component
                for payload in self.payloads.values()
                for component in payload["relief"]
            }
        )
        self.ends = np.array(
            sorted({float(payload["qol_years"]) for payload in self.payloads.values()})
        )
        self.starts = np.concatenate(([0.0], self.ends))[:-1]
        n_items, n_windows, n_components = (
            len(self.item_ids),
            len(self.ends),
            len(self.components),
        )
        self.relief = np.zeros((n_items, n_windows, n_components))
        self.mortality_allocation = np.zeros_like(self.relief)
        self.standalone_qol = np.zeros(n_items)
        self.standalone_mortality = np.zeros(n_items)
        losses: dict[str, float] = {}
        discount = (1.0 + self.discount_rate) ** -np.arange(
            math.ceil(max(self.ends, default=0)), dtype=float
        )
        window_discount = np.array(
            [
                _integral(discount, end) - _integral(discount, start)
                for start, end in zip(self.starts, self.ends)
            ]
        )
        for i, payload in enumerate(self.payloads.values()):
            years = float(payload["qol_years"])
            fractions = np.array(
                [
                    float(payload["relief"].get(component, 0.0))
                    for component in self.components
                ]
            )
            if np.any((fractions < 0) | (fractions > 1)):
                raise ValueError("guarded sleep relief must lie in [0, 1]")
            for component, loss in payload["annual_losses"].items():
                loss = float(loss)
                if component in losses and not math.isclose(
                    losses[component], loss, abs_tol=1e-12
                ):
                    raise ValueError(
                        "sleep overlap estimates use different baseline losses"
                    )
                losses[component] = loss
            self.relief[i] = (self.ends <= years)[:, None] * fractions
            expected_qol = sum(
                float(payload["annual_losses"].get(component, 0.0)) * fraction
                for component, fraction in zip(self.components, fractions)
            ) * _integral(discount, years)
            self.standalone_qol[i] = expected_qol
            component_qaly = payload.get("component_qol_qaly")
            if component_qaly is not None and not math.isclose(
                sum(component_qaly.values()), expected_qol, abs_tol=1e-12
            ):
                raise ValueError("component sleep QoL does not match guarded relief")
            mortality = max(0.0, float(payload.get("sleep_mortality_qaly", 0.0)))
            self.standalone_mortality[i] = mortality
            if mortality == 0:
                continue
            if "mortality_year_weights" not in payload:
                raise ValueError(
                    "sleep mortality overlap needs life-table exposure weights"
                )
            year_weights = np.asarray(payload["mortality_year_weights"], dtype=float)
            component_weights = np.array(
                [
                    float(payload["mortality_weights"].get(component, 0.0))
                    for component in self.components
                ]
            )
            weighted_relief = fractions * component_weights
            exposure = float(np.sum(weighted_relief)) * _integral(year_weights, years)
            if exposure <= 0:
                raise ValueError(
                    "positive sleep mortality QALY has no mortality exposure"
                )
            window_exposure = np.array(
                [
                    _integral(year_weights, end) - _integral(year_weights, start)
                    for start, end in zip(self.starts, self.ends)
                ]
            )
            self.mortality_allocation[i] = (
                self.relief[i]
                * component_weights[None, :]
                * window_exposure[:, None]
                * (mortality / exposure)
            )
        self.qol_weights = (
            window_discount[:, None]
            * np.array([losses.get(component, 0.0) for component in self.components])[
                None, :
            ]
        )

    def _values(self, item_ids: Sequence[str]) -> tuple[float, float, list[int]]:
        indices = [
            self.index[item_id]
            for item_id in dict.fromkeys(item_ids)
            if item_id in self.index
        ]
        if len(indices) < 2:
            return 0.0, 0.0, indices
        relief = self.relief[indices]
        summed = relief.sum(axis=0)
        combined = 1.0 - np.prod(1.0 - relief, axis=0)
        lost = np.maximum(summed - combined, 0.0)
        # When only one item targets a component, subtraction can leave a
        # roundoff-sized remainder; mathematically that interaction is zero.
        lost[np.count_nonzero(relief, axis=0) < 2] = 0.0
        qol_penalty = -float(np.sum(lost * self.qol_weights))
        proportional_loss = np.divide(
            lost, summed, out=np.zeros_like(lost), where=summed > 0
        )
        mortality_penalty = -float(
            np.sum(proportional_loss * self.mortality_allocation[indices].sum(axis=0))
        )
        return qol_penalty, mortality_penalty, indices

    def interaction_qaly(self, item_ids: Sequence[str]) -> float:
        """Fast scalar path used by exhaustive state enumeration."""
        qol_penalty, mortality_penalty, _ = self._values(item_ids)
        return qol_penalty + mortality_penalty

    def evaluate(self, item_ids: Sequence[str]) -> tuple[float, list[dict[str, Any]]]:
        qol_penalty, mortality_penalty, indices = self._values(item_ids)
        total = qol_penalty + mortality_penalty
        if not indices:
            return total, []
        return total, [
            {
                "id": "sleep_component_overlap",
                "description": "Multiplicative guarded relief within each sleep component and active window.",
                "item_ids": [self.item_ids[index] for index in indices],
                "penalty_qaly": total,
                "sleep_qol_interaction_qaly": qol_penalty,
                "sleep_mortality_interaction_qaly": mortality_penalty,
                "state_sleep_qol_qaly": float(self.standalone_qol[indices].sum())
                + qol_penalty,
                "state_sleep_mortality_qaly": float(
                    self.standalone_mortality[indices].sum()
                )
                + mortality_penalty,
                "mortality_method": "proportional component relief, weighted by lifetime mortality derivatives",
                "time_aware": True,
            }
        ]


def sleep_component_overlap(
    item_ids: Sequence[str],
    estimates_by_id: Mapping[str, Mapping[str, Any]],
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
) -> tuple[float, list[dict[str, Any]]]:
    """Convenience path for a single protocol state."""
    selected = {item_id: estimates_by_id[item_id] for item_id in item_ids}
    return SleepOverlapEvaluator(selected, discount_rate).evaluate(item_ids)


def mortality_approximation_bound(
    estimates_by_id: Mapping[str, Mapping[str, Any]],
    profile: Profile,
    baseline_hazard_multiplier: float,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
) -> dict[str, Any]:
    """Bound proportional mortality error for every subset of these inputs.

    The reference is the exact expected-quality life table with only the
    composed sleep HR acting on the common baseline, over each active window.
    Actual per-item slopes retain paired-simulation direct-HR interactions and
    Monte Carlo error; their range is included in this conservative bound.

    For any nonnegative log-hazard relief x <= x_max, each life-table partial
    derivative lies between a and b times its baseline derivative: a is the
    smallest q*exp(-x)/(1-q*exp(-x)) ratio and b is the largest survival ratio.
    Integrating along x gives a*linear <= exact <= b*linear. Proportional
    allocation is a weighted mean of the observed item slopes times that same
    linear exposure. Their extreme difference bounds all subsets, including
    infeasible supersets. No claim of exact joint direct-HR mortality is made.
    """
    evaluator = SleepOverlapEvaluator(estimates_by_id, discount_rate)
    log_baseline = math.log(max(1.0, baseline_hazard_multiplier))
    qx, quality_discount, survival = _mortality_arrays(
        profile, baseline_hazard_multiplier, discount_rate
    )
    zero = {
        "all_subsets_absolute_error_bound_qaly": 0.0,
        "all_items_absolute_error_qaly": 0.0,
    }
    if not evaluator.item_ids or log_baseline == 0 or not len(qx):
        return zero
    first = next(iter(evaluator.payloads.values()))
    component_weights = np.array(
        [
            float(first.get("mortality_weights", {}).get(component, 0.0))
            for component in evaluator.components
        ]
    )
    kernel = np.asarray(
        mortality_exposure_weights(profile, baseline_hazard_multiplier, discount_rate)
    )
    combined = 1.0 - np.prod(1.0 - evaluator.relief, axis=0)
    log_relief = log_baseline * (combined @ component_weights)
    year_multiplier = np.ones(len(qx))
    year_max_log = np.zeros(len(qx))
    linear_max = 0.0
    for start, end, value in zip(evaluator.starts, evaluator.ends, log_relief):
        linear_max += value * (_integral(kernel, end) - _integral(kernel, start))
        for year in range(max(0, int(start)), min(len(qx), math.ceil(end))):
            fraction = max(0.0, min(end, year + 1.0) - max(start, year))
            year_multiplier[year] += fraction * math.expm1(-value)
            year_max_log[year] = max(year_max_log[year], value)
    if linear_max <= 0:
        return zero
    slopes = []
    for item_id, payload in evaluator.payloads.items():
        weighted = sum(
            float(payload["relief"].get(component, 0.0)) * weight
            for component, weight in zip(evaluator.components, component_weights)
        )
        linear = (
            log_baseline * weighted * _integral(kernel, float(payload["qol_years"]))
        )
        if linear > 0:
            slopes.append(
                evaluator.standalone_mortality[evaluator.index[item_id]] / linear
            )
    minimum_multiplier = np.exp(-year_max_log)
    lower = float(np.min(minimum_multiplier * (1 - qx) / (1 - qx * minimum_multiplier)))
    upper = float(np.prod((1 - qx * minimum_multiplier) / (1 - qx)))
    error_bound = max(abs(min(slopes) - upper), abs(max(slopes) - lower)) * linear_max
    state_survival = np.concatenate(([1.0], np.cumprod(1 - qx * year_multiplier)))[:-1]
    exact = float(np.sum((state_survival - survival) * quality_discount))
    _, mortality_penalty, _ = evaluator._values(evaluator.item_ids)
    approximate = float(evaluator.standalone_mortality.sum()) + mortality_penalty
    return {
        "all_subsets_absolute_error_bound_qaly": error_bound,
        "all_items_absolute_error_qaly": abs(approximate - exact),
        "all_items_exact_sleep_mortality_qaly": exact,
        "all_items_proportional_sleep_mortality_qaly": approximate,
        "reference": "Expected-quality life table with composed sleep HR on the common baseline; direct HRs excluded.",
        "scope": "Every subset of the supplied items, including exclusive-group-infeasible supersets.",
    }
