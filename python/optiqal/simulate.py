"""
Monte Carlo Simulation Module

QALY estimation by forward simulation over the priors registry.

Every public entry point (:func:`simulate_qaly`, :func:`simulate_qaly_profile`
and :func:`simulate_qaly_profile_vectorized`) runs the one integrator in
:func:`simulate_qaly_profile_vectorized`.
"""

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Union

import numpy as np

from .defaults import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    validate_qaly_discount_rate,
)
from .intervention import (
    HarmEffect,
    InteractionRule,
    Intervention,
    allocate_interaction_rule,
    validate_effect_timing,
)
from .lifecycle import (
    QUALITY_WEIGHT_STD,
    get_cause_fraction,
    get_mortality_rate,
    get_quality_weight,
)
from .profile import (
    Profile,
    get_baseline_mortality_multiplier,
    get_intervention_modifier,
)


@dataclass
class SimulationResult:
    """Result of Monte Carlo QALY simulation."""

    median: float
    mean: float
    std: float
    ci95: tuple  # (low, high)
    ci50: tuple  # (low, high)
    prob_positive: float
    prob_more_than_one_year: float

    # Pathway contributions
    cvd_contribution: float
    cancer_contribution: float
    other_contribution: float

    # Life years
    life_years_gained: float

    # 80% interval (p10, p90) of the net-QALY draws, for surfacing uncertainty.
    ci80: tuple = (0.0, 0.0)

    # Posterior decision metrics
    prob_negative: float = 0.0
    expected_upside: float = 0.0
    expected_downside: float = 0.0
    conditional_upside: float = 0.0
    conditional_downside: float = 0.0

    # Confounding
    causal_fraction_mean: Optional[float] = None
    causal_fraction_ci: Optional[tuple] = None

    # Posterior HR — what the simulator actually applies at the life-table level
    # after publication-bias correction and Bayesian confounding draws. This is
    # the HR a reader should compare items on, not the publication-bias-only
    # display HR. None when the intervention has no direct mortality effect.
    posterior_hr_mean: Optional[float] = None
    posterior_hr_median: Optional[float] = None
    posterior_hr_ci95: Optional[tuple] = None

    # Cost (survival-weighted discounted)
    expected_discounted_cost_factor: float = 1.0  # Multiply by annual_cost for total
    expected_qol_factor: float = 0.0  # Multiply annual utility effect for total
    expected_qol_weights: tuple[float, ...] = ()
    expected_harm_qalys: float = 0.0
    expected_interaction_harm_qalys: float = 0.0

    # Adherence / policy views
    annual_persistence: float = 1.0
    continuation_adjusted_mean: float = 0.0
    continuation_adjusted_life_years_gained: float = 0.0
    continuation_adjusted_cost_factor: float = 1.0
    continuation_adjusted_qol_factor: float = 0.0
    one_year_mean: float = 0.0
    one_year_life_years_gained: float = 0.0
    one_year_cost_factor: float = 1.0
    one_year_qol_factor: float = 1.0

    # Settings
    n_simulations: int = 10000
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE


def _posterior_decision_metrics(qaly_gains: np.ndarray) -> dict[str, float]:
    """Compute decision-relevant posterior summaries from simulation draws."""
    positive = qaly_gains[qaly_gains > 0]
    negative = qaly_gains[qaly_gains < 0]

    return {
        "prob_positive": float(np.mean(qaly_gains > 0)),
        "prob_negative": float(np.mean(qaly_gains < 0)),
        "prob_more_than_one_year": float(np.mean(qaly_gains > 1)),
        "expected_upside": float(np.mean(np.clip(qaly_gains, 0, None))),
        "expected_downside": float(np.mean(np.clip(qaly_gains, None, 0))),
        "conditional_upside": float(np.mean(positive)) if positive.size else 0.0,
        "conditional_downside": float(np.mean(negative)) if negative.size else 0.0,
    }


def _build_simulation_result(
    qaly_gains: np.ndarray,
    cvd_contribution: float,
    cancer_contribution: float,
    other_contribution: float,
    life_years_gained: float,
    *,
    causal_fraction_mean: Optional[float] = None,
    causal_fraction_ci: Optional[tuple] = None,
    posterior_hr_mean: Optional[float] = None,
    posterior_hr_median: Optional[float] = None,
    posterior_hr_ci95: Optional[tuple] = None,
    expected_discounted_cost_factor: float = 1.0,
    expected_qol_factor: float = 0.0,
    expected_qol_weights: tuple[float, ...] = (),
    expected_harm_qalys: float = 0.0,
    expected_interaction_harm_qalys: float = 0.0,
    annual_persistence: float = 1.0,
    continuation_adjusted_mean: float = 0.0,
    continuation_adjusted_life_years_gained: float = 0.0,
    continuation_adjusted_cost_factor: float = 1.0,
    continuation_adjusted_qol_factor: float = 0.0,
    one_year_mean: float = 0.0,
    one_year_life_years_gained: float = 0.0,
    one_year_cost_factor: float = 1.0,
    one_year_qol_factor: float = 1.0,
    n_simulations: int = 10000,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
) -> SimulationResult:
    """Create a consistent SimulationResult from posterior draws."""
    metrics = _posterior_decision_metrics(qaly_gains)

    return SimulationResult(
        median=float(np.median(qaly_gains)),
        mean=float(np.mean(qaly_gains)),
        std=float(np.std(qaly_gains)),
        ci95=(
            float(np.percentile(qaly_gains, 2.5)),
            float(np.percentile(qaly_gains, 97.5)),
        ),
        ci80=(
            float(np.percentile(qaly_gains, 10)),
            float(np.percentile(qaly_gains, 90)),
        ),
        ci50=(
            float(np.percentile(qaly_gains, 25)),
            float(np.percentile(qaly_gains, 75)),
        ),
        prob_positive=metrics["prob_positive"],
        prob_negative=metrics["prob_negative"],
        prob_more_than_one_year=metrics["prob_more_than_one_year"],
        expected_upside=metrics["expected_upside"],
        expected_downside=metrics["expected_downside"],
        conditional_upside=metrics["conditional_upside"],
        conditional_downside=metrics["conditional_downside"],
        cvd_contribution=cvd_contribution,
        cancer_contribution=cancer_contribution,
        other_contribution=other_contribution,
        life_years_gained=life_years_gained,
        causal_fraction_mean=causal_fraction_mean,
        causal_fraction_ci=causal_fraction_ci,
        posterior_hr_mean=posterior_hr_mean,
        posterior_hr_median=posterior_hr_median,
        posterior_hr_ci95=posterior_hr_ci95,
        expected_discounted_cost_factor=expected_discounted_cost_factor,
        expected_qol_factor=expected_qol_factor,
        expected_qol_weights=expected_qol_weights,
        expected_harm_qalys=expected_harm_qalys,
        expected_interaction_harm_qalys=expected_interaction_harm_qalys,
        annual_persistence=annual_persistence,
        continuation_adjusted_mean=continuation_adjusted_mean,
        continuation_adjusted_life_years_gained=continuation_adjusted_life_years_gained,
        continuation_adjusted_cost_factor=continuation_adjusted_cost_factor,
        continuation_adjusted_qol_factor=continuation_adjusted_qol_factor,
        one_year_mean=one_year_mean,
        one_year_life_years_gained=one_year_life_years_gained,
        one_year_cost_factor=one_year_cost_factor,
        one_year_qol_factor=one_year_qol_factor,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
        cost_discount_rate=cost_discount_rate,
    )


def _zero_horizon_result(
    n_simulations: int,
    *,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
    annual_persistence: float = 1.0,
) -> SimulationResult:
    """Return the result for a profile with no remaining modeled years.

    Nothing is simulated, so every QALY summary is exactly zero and every
    exposure factor (cost, continuation cost, one-year cost, and the matching
    utility factors) is zero too: with no modeled year there is nobody alive
    to pay for, take, or benefit from the intervention.
    """
    discount_rate = validate_qaly_discount_rate(discount_rate)
    return SimulationResult(
        median=0,
        mean=0,
        std=0,
        ci95=(0, 0),
        ci50=(0, 0),
        prob_positive=0.0,
        prob_negative=0.0,
        prob_more_than_one_year=0.0,
        expected_upside=0.0,
        expected_downside=0.0,
        conditional_upside=0.0,
        conditional_downside=0.0,
        cvd_contribution=0,
        cancer_contribution=0,
        other_contribution=0,
        life_years_gained=0,
        expected_discounted_cost_factor=0.0,
        expected_qol_factor=0.0,
        expected_qol_weights=(),
        expected_harm_qalys=0.0,
        expected_interaction_harm_qalys=0.0,
        annual_persistence=annual_persistence,
        continuation_adjusted_mean=0.0,
        continuation_adjusted_life_years_gained=0.0,
        continuation_adjusted_cost_factor=0.0,
        continuation_adjusted_qol_factor=0.0,
        one_year_mean=0.0,
        one_year_life_years_gained=0.0,
        one_year_cost_factor=0.0,
        one_year_qol_factor=0.0,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
        cost_discount_rate=cost_discount_rate,
    )


def effective_qol_factor_for_years(
    expected_qol_weights: Iterable[float],
    years: float,
    fallback_factor: float = 0.0,
) -> float:
    """Accumulate survival-weighted annual utility exposure over a bounded duration."""
    if years <= 0:
        return 0.0

    weights = tuple(float(weight) for weight in expected_qol_weights)
    if not weights:
        if fallback_factor <= 0:
            return 0.0
        return float(min(years, fallback_factor))

    whole_years = int(np.floor(years))
    fractional_year = float(years - whole_years)

    factor = float(sum(weights[:whole_years]))
    if fractional_year > 0 and whole_years < len(weights):
        factor += fractional_year * weights[whole_years]
    return factor


def mortality_qaly_for_combined_hr(
    profile: Profile,
    combined_hr: float,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    baseline_hazard_multiplier: float = 1.0,
    max_age: int = 100,
) -> float:
    """Deterministic mortality QALY gain from a flat all-cause hazard ratio.

    This is a *relative* integrator used only for combining a stack: applying a
    single all-cause HR flat to baseline mortality and integrating QALYs once.
    Its absolute level does NOT equal the Monte Carlo per-item ``mort_qaly``
    (the MC mean averages QALY over the whole HR distribution and quality-weight
    draws, which is convex in HR). To stay consistent with the per-item sim,
    callers should NOT pass the raw posterior HR; instead derive each item's
    effective HR with :func:`effective_hr_for_mortality_qaly` (which inverts this
    function against the item's own sim ``mort_qaly``), combine those effective
    HRs multiplicatively, and integrate once here. That makes a single-item
    "stack" reproduce its sim value exactly while correctly avoiding the
    shared-survival double-count of summing per-item QALYs across a stack.
    """
    discount_rate = validate_qaly_discount_rate(discount_rate)
    n_years = max_age - profile.age
    if n_years <= 0:
        return 0.0

    baseline_mortality_multiplier = get_baseline_mortality_multiplier(profile)
    ages = profile.age + np.arange(n_years)
    base_qx = np.minimum(
        np.array([get_mortality_rate(int(a), profile.sex) for a in ages])
        * baseline_mortality_multiplier
        * float(max(baseline_hazard_multiplier, 0.0)),
        0.99,
    )
    quality = np.array([get_quality_weight(int(a)) for a in ages])
    discount = (1.0 / (1.0 + discount_rate)) ** np.arange(n_years)

    def _qaly(multiplier: float) -> float:
        policy_qx = np.minimum(base_qx * multiplier, 0.99)
        survival = np.cumprod(1 - policy_qx)
        survival = np.concatenate([[1.0], survival[:-1]])
        return float(np.sum(survival * quality * discount))

    return _qaly(combined_hr) - _qaly(1.0)


def effective_hr_for_mortality_qaly(
    profile: Profile,
    mortality_qaly: float,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    baseline_hazard_multiplier: float = 1.0,
    max_age: int = 100,
) -> float:
    """Invert :func:`mortality_qaly_for_combined_hr` for a single item.

    Returns the flat all-cause HR whose deterministic integral reproduces the
    item's Monte Carlo ``mortality_qaly``. Combining these effective HRs
    multiplicatively (then integrating once) gives a stack total that reproduces
    each item alone and is correctly sub-additive across items. Items with no
    mortality benefit (``mortality_qaly <= 0``) map to HR 1.0.
    """
    if mortality_qaly <= 0:
        return 1.0

    def gain(hr: float) -> float:
        return mortality_qaly_for_combined_hr(
            profile,
            hr,
            discount_rate=discount_rate,
            baseline_hazard_multiplier=baseline_hazard_multiplier,
            max_age=max_age,
        )

    # gain is monotone decreasing in hr (lower hr -> larger gain). Bracket and
    # bisect; clamp to the achievable range so an out-of-range target is capped.
    lo, hi = 1e-3, 1.0
    max_gain = gain(lo)
    if mortality_qaly >= max_gain:
        return lo
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if gain(mid) >= mortality_qaly:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _series_phi(x: np.ndarray) -> np.ndarray:
    """Return ``(1 - exp(-x) * (1 + x)) / x**2`` for ``x >= 0`` (1/2 at 0).

    The direct formula cancels catastrophically as ``x -> 0``, so small
    arguments use its Taylor series ``sum_{k>=2} (-1)**k (k-1)/k! x**(k-2)``;
    fourteen terms reach machine precision below the 0.05 switch point.
    """
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    small = x < 0.05
    xs = x[small]
    series = np.zeros_like(xs)
    for k in range(2, 16):
        series += (-1) ** k * (k - 1) / math.factorial(k) * xs ** (k - 2)
    out[small] = series
    xl = x[~small]
    out[~small] = (-np.expm1(-xl) - xl * np.exp(-xl)) / xl**2
    return out


def _series_psi(x: np.ndarray) -> np.ndarray:
    """Return ``(1 - exp(-x)) / x`` for ``x >= 0`` (exactly 1 at 0)."""
    x = np.asarray(x, dtype=float)
    out = np.ones_like(x)
    nonzero = x != 0
    out[nonzero] = -np.expm1(-x[nonzero]) / x[nonzero]
    return out


def mortality_effect_fraction(
    n_years: int,
    onset_delay: float = 0.0,
    ramp_up: float = 0.0,
    decay_rate: float = 0.0,
) -> np.ndarray:
    """Average share of an intervention's full mortality effect in each model year.

    The effect fraction at continuous time ``tau`` (years since starting) is

    - ``0`` for ``tau < onset_delay``;
    - ``(tau - onset_delay) / ramp_up`` while ramping up, on
      ``[onset_delay, onset_delay + ramp_up)``;
    - ``1`` afterwards;

    multiplied by ``exp(-decay_rate * (tau - onset_delay))`` from onset on when
    ``decay_rate > 0``. Entry ``t`` of the result is the exact average of that
    fraction over ``[t, t + 1)``, from the closed-form integrals of the linear
    and exponential pieces. With no declared timing every entry is exactly 1.
    """
    onset = validate_effect_timing("onset_delay", onset_delay)
    ramp = validate_effect_timing("ramp_up", ramp_up)
    decay = validate_effect_timing("decay_rate", decay_rate)

    start = np.arange(n_years, dtype=float)
    end = start + 1.0
    ramp_end = onset + ramp

    # Ramp piece, in time since onset s: integral of (s / ramp) exp(-decay s),
    # whose antiderivative from 0 is s**2 * phi(decay s) / ramp.
    if ramp > 0:
        ramp_low = np.clip(start, onset, ramp_end) - onset
        ramp_high = np.clip(end, onset, ramp_end) - onset
        ramp_part = (
            ramp_high**2 * _series_phi(decay * ramp_high)
            - ramp_low**2 * _series_phi(decay * ramp_low)
        ) / ramp
    else:
        ramp_part = np.zeros(n_years)

    # Full-effect piece: integral of exp(-decay s) over [low, high), which is
    # exp(-decay low) * width * psi(decay * width).
    full_low = np.maximum(start, ramp_end)
    width = np.maximum(end, ramp_end) - full_low
    full_part = np.exp(-decay * (full_low - onset)) * width * _series_psi(decay * width)

    return np.clip(ramp_part + full_part, 0.0, 1.0)


def _intervention_effect_fraction(
    intervention: Intervention, n_years: int
) -> np.ndarray:
    """Per-year effect fraction from the intervention's declared mortality timing."""
    mortality = intervention.mortality
    if mortality is None:
        return np.ones(n_years)
    return mortality_effect_fraction(
        n_years,
        onset_delay=mortality.onset_delay,
        ramp_up=mortality.ramp_up,
        decay_rate=mortality.decay_rate,
    )


def _simulate_reversible_policy(
    base_qx: np.ndarray,
    policy_hr: np.ndarray,
    exposure_curve: np.ndarray,
    effect_fraction: np.ndarray,
    quality: np.ndarray,
    qaly_discount: np.ndarray,
    cost_discount: np.ndarray,
    baseline_qalys_total: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float, np.ndarray, np.ndarray]:
    """Simulate a reversible intervention under an adherence policy.

    The all-cause hazard ratio ``policy_hr`` (one per simulation) is applied
    flat to baseline mortality. In model year ``t`` the hazard multiplier is
    ``1 + exposure_curve[t] * effect_fraction[t] * (policy_hr - 1)``: the
    adherence/active-duration curve times the share of the effect the declared
    onset, ramp-up and decay allow (see :func:`mortality_effect_fraction`).
    Cost and utility exposure follow ``exposure_curve`` alone, because the
    intervention is paid for and taken from the first year whether or not its
    mortality effect has started. The cause-specific pathway exponents are used
    only for the *reported* cvd/cancer/other decomposition (see
    :func:`simulate_qaly_profile_vectorized`), never for this survival
    integration — applying them here attenuated every effect toward the null in
    an age-dependent way.
    """
    effect_curve = exposure_curve * effect_fraction
    excess = (policy_hr - 1.0)[:, None]  # (n_simulations, 1)
    policy_multiplier = 1.0 + effect_curve[None, :] * excess
    # The lower clip keeps survival non-increasing even for a nonpositive
    # sampled HR; for positive HRs it never binds.
    policy_qx = np.clip(base_qx[None, :] * policy_multiplier, 0.0, 0.99)

    policy_survival = np.cumprod(1 - policy_qx, axis=1)
    policy_survival = np.concatenate(
        [np.ones((policy_survival.shape[0], 1)), policy_survival[:, :-1]],
        axis=1,
    )

    policy_qalys_per_year = policy_survival * quality * qaly_discount[None, :]
    policy_qalys_total = np.sum(policy_qalys_per_year, axis=1)
    policy_life_years = np.sum(policy_survival, axis=1)
    policy_qaly_gains = policy_qalys_total - baseline_qalys_total

    mean_policy_survival = np.mean(policy_survival, axis=0)
    policy_cost_factor = float(
        np.sum(mean_policy_survival * exposure_curve * cost_discount)
    )
    policy_qol_factor = float(
        np.sum(mean_policy_survival * exposure_curve * qaly_discount)
    )
    policy_qol_weights = mean_policy_survival * exposure_curve * qaly_discount

    return (
        policy_qaly_gains,
        policy_life_years,
        policy_cost_factor,
        policy_qol_factor,
        policy_survival,
        policy_qol_weights,
    )


def _active_years_curve(n_years: int, active_years: Optional[float]) -> np.ndarray:
    """Return an annual exposure curve with a possible fractional final year."""
    if active_years is None:
        return np.ones(n_years)
    active_years = float(active_years)
    if active_years <= 0:
        return np.zeros(n_years)
    curve = np.zeros(n_years)
    full_years = min(int(np.floor(active_years)), n_years)
    curve[:full_years] = 1.0
    remainder = active_years - full_years
    if remainder > 0 and full_years < n_years:
        curve[full_years] = remainder
    return curve


def _sample_distribution(
    dist,
    n_simulations: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Sample a Distribution using the local generator for independence."""
    return dist.sample(n_simulations, random_state=rng)


def _spawn_generators(
    random_state: Optional[int],
    count: int,
) -> tuple[np.random.Generator, ...]:
    """Derive reproducible, independent semantic streams from one seed."""
    return tuple(
        np.random.default_rng(child)
        for child in np.random.SeedSequence(random_state).spawn(count)
    )


def _has_direct_mortality_effect(intervention: Intervention) -> bool:
    """Return whether an intervention has a non-null direct mortality arm."""
    if intervention.mortality is None:
        return False
    hazard_ratio = intervention.mortality.hazard_ratio
    return not (
        hazard_ratio.type == "point" and float(hazard_ratio.params["value"]) == 1.0
    )


def _triggered_interaction_rules(
    intervention: Intervention,
    active_interaction_tags: Optional[Iterable[str]],
) -> list[InteractionRule]:
    """Return stack-aware interaction rules activated by the current tag context."""
    tag_counts = Counter(active_interaction_tags or [])
    for tag in intervention.interaction_tags:
        tag_counts[tag] += 1

    triggered: list[InteractionRule] = []
    for rule in intervention.interaction_rules:
        threshold = rule.minimum_matches or len(rule.requires_tags)
        matches = sum(tag_counts[tag] for tag in rule.requires_tags)
        if matches >= threshold and all(
            tag_counts[tag] > 0 for tag in rule.requires_tags
        ):
            triggered.append(allocate_interaction_rule(rule, matches))

    return triggered


def _events_below_cap_probability(
    event_chance: np.ndarray,
    max_events: Optional[int],
) -> np.ndarray:
    """Probability that fewer than ``max_events`` events occurred before each year.

    ``event_chance[d, t]`` is the chance of an event in year ``t`` for draw
    ``d``; years are independent, so the count of events in years before
    ``t`` is Poisson-binomial. Entry ``[d, t]`` of the result is
    ``P(N_<t < max_events)``, from a dynamic program over the count
    distribution truncated at ``max_events - 1``. ``None`` means no cap.
    """
    n_draws, n_years = event_chance.shape
    if max_events is None:
        return np.ones((n_draws, n_years))
    if isinstance(max_events, bool) or int(max_events) != max_events:
        raise ValueError(
            f"max_events must be a nonnegative integer or None, got {max_events!r}"
        )
    cap = int(max_events)
    if cap < 0:
        raise ValueError(
            f"max_events must be a nonnegative integer or None, got {max_events!r}"
        )
    if cap == 0:
        return np.zeros((n_draws, n_years))
    if cap >= n_years:
        # At most n_years - 1 events precede any modeled year, so the cap never binds.
        return np.ones((n_draws, n_years))
    if cap == 1:
        # P(N_<t = 0) = prod_{u<t} (1 - chance[u]).
        no_event = np.cumprod(1.0 - event_chance, axis=1)
        return np.concatenate([np.ones((n_draws, 1)), no_event[:, :-1]], axis=1)

    count_probability = np.zeros((n_draws, cap))
    count_probability[:, 0] = 1.0
    below_cap = np.empty((n_draws, n_years))
    for year in range(n_years):
        below_cap[:, year] = count_probability.sum(axis=1)
        chance = event_chance[:, year : year + 1]
        shifted = np.zeros_like(count_probability)
        shifted[:, 1:] = count_probability[:, :-1] * chance
        count_probability = count_probability * (1.0 - chance) + shifted
    return below_cap


def expected_event_loss(
    survival: np.ndarray,
    exposure: np.ndarray,
    discount: np.ndarray,
    event_probability: Union[float, np.ndarray],
    event_loss: Union[float, np.ndarray],
    max_events: Optional[int] = 1,
) -> np.ndarray:
    """Expected discounted QALY loss from a discrete harmful event.

    In model year ``t`` a person alive at the start of the year (probability
    ``survival[t]``) has the event with chance ``q[t] = exposure[t] *
    event_probability``, at most once per year and independently of other
    years; the event does not change survival. Each counted event costs
    ``event_loss`` QALYs valued at ``discount[t]``, the same start-of-year
    factor year-``t`` QALYs receive. Only the first ``max_events`` events in
    time count (``None`` counts every event), so the expected loss is::

        event_loss * sum_t discount[t] * survival[t] * q[t] * P(N_<t < max_events)

    where ``N_<t`` is the number of events in earlier years. For
    ``max_events == 1`` the last factor is ``prod_{u<t} (1 - q[u])``: the
    first event can only happen in years still event-free.

    ``survival`` is ``(n_years,)`` or ``(n_draws, n_years)``; ``exposure`` is
    ``(n_years,)`` or ``(n_draws, n_years)``; ``discount`` is ``(n_years,)``;
    ``event_probability`` and ``event_loss`` are scalars or ``(n_draws,)``.
    Probabilities are clipped to [0, 1] and losses to >= 0. Returns the
    nonnegative expected loss per draw, shape ``(n_draws,)``.
    """
    survival = np.atleast_2d(np.asarray(survival, dtype=float))
    exposure = np.atleast_2d(np.asarray(exposure, dtype=float))
    discount = np.asarray(discount, dtype=float)[None, :]
    probability = np.clip(np.asarray(event_probability, dtype=float), 0.0, 1.0)
    loss = np.clip(np.asarray(event_loss, dtype=float), 0.0, None).reshape(-1)

    event_chance = np.clip(exposure * probability.reshape(-1, 1), 0.0, 1.0)
    n_draws = max(survival.shape[0], event_chance.shape[0], loss.shape[0])
    event_chance = np.broadcast_to(event_chance, (n_draws, survival.shape[1]))
    below_cap = _events_below_cap_probability(event_chance, max_events)
    expected_events = np.sum(discount * survival * event_chance * below_cap, axis=1)
    return loss * expected_events


@dataclass(frozen=True)
class _SampledHarm:
    """One harm source's parameter draws, shared by every policy view."""

    annual_qaly_loss: Optional[np.ndarray]
    event_probability: Optional[np.ndarray]
    event_qaly_loss: Optional[np.ndarray]
    max_events: Optional[int]


def _sample_harm_parameters(
    harm_sources: list[Union[HarmEffect, InteractionRule]],
    rng: np.random.Generator,
    n_simulations: int,
) -> list[_SampledHarm]:
    """Draw each harm source's uncertain parameters once, in source order."""
    sampled = []
    for harm in harm_sources:
        annual_qaly_loss = None
        if getattr(harm, "annual_qaly_loss", None) is not None:
            annual_qaly_loss = np.clip(
                _sample_distribution(harm.annual_qaly_loss, n_simulations, rng),
                0,
                None,
            )
        event_probability = event_qaly_loss = None
        if (
            getattr(harm, "event_probability", None) is not None
            and getattr(harm, "event_qaly_loss", None) is not None
        ):
            event_probability = np.clip(
                _sample_distribution(harm.event_probability, n_simulations, rng),
                0,
                1,
            )
            event_qaly_loss = np.clip(
                _sample_distribution(harm.event_qaly_loss, n_simulations, rng),
                0,
                None,
            )
        sampled.append(
            _SampledHarm(
                annual_qaly_loss=annual_qaly_loss,
                event_probability=event_probability,
                event_qaly_loss=event_qaly_loss,
                max_events=getattr(harm, "max_events", 1),
            )
        )
    return sampled


def _harm_draws_for_policy(
    sampled_harms: list[_SampledHarm],
    policy_survival: np.ndarray,
    exposure_curve: np.ndarray,
    qaly_discount: np.ndarray,
    n_simulations: int,
) -> np.ndarray:
    """Expected harm QALYs per draw for one policy view.

    Each draw carries the expected loss given that draw's sampled parameters
    and survival curve, not a sampled realization of whether an event
    happened. That matches how death is handled: each draw integrates the
    expected survival curve rather than sampling an age at death. The draws
    therefore describe parameter (second-order) uncertainty only, the
    probabilistic-sensitivity-analysis convention, so the probabilities and
    intervals built from them do not mix in individual event luck.
    """
    harm_draws = np.zeros(n_simulations)
    if not sampled_harms:
        return harm_draws

    exposure_factor = np.sum(
        policy_survival * exposure_curve[None, :] * qaly_discount[None, :],
        axis=1,
    )
    for harm in sampled_harms:
        if harm.annual_qaly_loss is not None:
            harm_draws -= harm.annual_qaly_loss * exposure_factor
        if harm.event_probability is not None:
            harm_draws -= expected_event_loss(
                policy_survival,
                exposure_curve,
                qaly_discount,
                harm.event_probability,
                harm.event_qaly_loss,
                harm.max_events,
            )
    return harm_draws


def _simulate_harm_draws(
    harm_sources: list[Union[HarmEffect, InteractionRule]],
    policy_survival: np.ndarray,
    continuation_curve: np.ndarray,
    qaly_discount: np.ndarray,
    rng: np.random.Generator,
    n_simulations: int,
) -> np.ndarray:
    """Sample harm parameters and evaluate them on one policy view's time grid."""
    return _harm_draws_for_policy(
        _sample_harm_parameters(harm_sources, rng, n_simulations),
        policy_survival,
        continuation_curve,
        qaly_discount,
        n_simulations,
    )


def simulate_qaly_profile_vectorized(
    intervention: Intervention,
    profile: Profile,
    n_simulations: int = 10000,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
    annual_persistence: float = 1.0,
    active_interaction_tags: Optional[Iterable[str]] = None,
    baseline_hazard_multiplier: float = 1.0,
    global_intervention_hr_multiplier: float = 1.0,
    active_years: Optional[float] = None,
    apply_confounding: bool = True,
    random_state: Optional[int] = None,
    return_qaly_gains: bool = False,
    apply_intervention_modifier: bool = True,
) -> Union[SimulationResult, tuple[SimulationResult, np.ndarray]]:
    """
    Vectorized Monte Carlo simulation - ~100x faster than loop version.

    Uses NumPy broadcasting to process all simulations at once. This is the one
    integrator behind every public ``simulate_*`` entry point.

    Args:
        discount_rate: Discount rate for QALYs (default 3% reference-case rate).
        cost_discount_rate: Discount rate for costs (default 3% reference-case rate).
        annual_persistence: Probability of renewing the intervention each year
            after the current year. Used to compute continuation-adjusted and
            one-year-only policy views for reversible interventions.
        active_years: Optional hard active-duration window for the primary policy.
            When provided, benefits, harms, and costs are only applied over this
            many years, with a prorated final year.
        apply_intervention_modifier: Whether to apply the profile's intervention
            effect modifier to the sampled HR. Callers that have already baked
            the modifier into the HR (e.g. the combined-intervention path) pass
            False to avoid double-counting it.
        return_qaly_gains: When true, also return the simulated net QALY draws.

    The declared mortality timing (``onset_delay``, ``ramp_up``,
    ``decay_rate``) scales the hazard-ratio effect year by year in the primary,
    continuation and one-year views (see :func:`mortality_effect_fraction`).
    Costs, harms and utility exposure start with the intervention, not with
    its mortality effect.

    Harm parameters are drawn once per call and shared by all three views, so
    the views differ only by their exposure, never by resampling noise; with
    ``annual_persistence=1`` the continuation view equals the primary view
    exactly. Event harms enter each draw as the expected discounted loss given
    that draw's parameters (see :func:`expected_event_loss`).
    """
    discount_rate = validate_qaly_discount_rate(discount_rate)
    quality_rng, hr_rng, causal_rng, harm_rng = _spawn_generators(random_state, 4)
    persistence = float(np.clip(annual_persistence, 0.0, 1.0))

    # Profile adjustments
    baseline_mortality_multiplier = get_baseline_mortality_multiplier(profile)
    intervention_effect_modifier = (
        get_intervention_modifier(profile, intervention.category)
        if apply_intervention_modifier
        else 1.0
    )

    # Pre-compute year arrays (static for all simulations)
    max_age = 100
    n_years = max_age - profile.age
    if n_years <= 0:
        # Profile age is at or beyond the modeled horizon, so there are no
        # remaining life-years to simulate. Return a null result instead of
        # crashing on empty/negative-length arrays below.
        zero = _zero_horizon_result(
            n_simulations,
            discount_rate=discount_rate,
            cost_discount_rate=cost_discount_rate,
            annual_persistence=persistence,
        )
        return (zero, np.zeros(n_simulations)) if return_qaly_gains else zero
    years = np.arange(n_years)
    ages = profile.age + years

    # Base mortality rates, quality weights, discounts, cause fractions
    base_qx = np.array([get_mortality_rate(int(a), profile.sex) for a in ages])
    base_qx = np.minimum(
        base_qx
        * baseline_mortality_multiplier
        * float(max(baseline_hazard_multiplier, 0.0)),
        0.99,
    )
    base_quality = np.array([get_quality_weight(int(a)) for a in ages])
    discount = (1 / (1 + discount_rate)) ** years
    cost_discount = (1 / (1 + cost_discount_rate)) ** years

    # Cause fractions (n_years, 3)
    cause_fracs = np.array(
        [
            [get_cause_fraction(int(a))[k] for k in ["cvd", "cancer", "other"]]
            for a in ages
        ]
    )

    # Sample quality weight offsets (MEPS calibration: within-age σ=0.117)
    # Each simulation gets a person-specific offset that persists across years
    quality_offsets = quality_rng.normal(
        0, QUALITY_WEIGHT_STD, n_simulations
    )  # (n_simulations,)
    # Quality weights vary by simulation: (n_simulations, n_years)
    quality = np.clip(base_quality[None, :] + quality_offsets[:, None], 0.1, 1.0)

    # Sample HRs and causal fractions (n_simulations,)
    has_direct_mortality_effect = _has_direct_mortality_effect(intervention)
    if has_direct_mortality_effect:
        hr_samples = intervention.mortality.hazard_ratio.sample(n_simulations, hr_rng)

        if intervention_effect_modifier != 1.0:
            hr_samples = np.exp(np.log(hr_samples) * intervention_effect_modifier)

        if apply_confounding and intervention.confounding_prior is not None:
            causal_samples = intervention.confounding_prior.sample(
                n_simulations, causal_rng
            )
            causal_fraction_mean = intervention.confounding_prior.mean
            causal_fraction_ci = intervention.confounding_prior.ci(0.95)
        else:
            causal_samples = np.ones(n_simulations)
            causal_fraction_mean = None
            causal_fraction_ci = None

        # Adjust HRs for confounding: log(adjusted_hr) = causal_fraction * log(observed_hr).
        # This all-cause HR is applied flat to mortality (see _simulate_reversible_policy);
        # the 1.3/0.8/0.6 pathway exponents below feed only the reported decomposition.
        adjusted_hrs = np.exp(causal_samples * np.log(hr_samples))  # (n_simulations,)
        if global_intervention_hr_multiplier != 1.0:
            adjusted_hrs = np.clip(
                adjusted_hrs * global_intervention_hr_multiplier, 1e-6, None
            )
    else:
        adjusted_hrs = np.full(
            n_simulations, max(global_intervention_hr_multiplier, 1e-6)
        )
        causal_fraction_mean = None
        causal_fraction_ci = None

    # Baseline survival (deterministic, same for all simulations)
    baseline_survival = np.cumprod(1 - base_qx)
    baseline_survival = np.concatenate(
        [[1.0], baseline_survival[:-1]]
    )  # Shift for start-of-year
    baseline_life_years = np.sum(baseline_survival)

    # Baseline QALYs now vary by simulation due to quality weight heterogeneity
    # baseline_qalys_per_year: (n_simulations, n_years)
    baseline_qalys_per_year = baseline_survival[None, :] * quality * discount[None, :]
    baseline_qalys_total = np.sum(baseline_qalys_per_year, axis=1)  # (n_simulations,)

    effect_fraction = _intervention_effect_fraction(intervention, n_years)
    full_curve = _active_years_curve(n_years, active_years)
    continuation_curve = full_curve * (persistence**years)
    one_year_curve = np.zeros(n_years)
    one_year_curve[0] = 1.0

    (
        qaly_gains,
        intervention_life_years,
        expected_discounted_cost_factor,
        expected_qol_factor,
        full_survival,
        full_qol_weights,
    ) = _simulate_reversible_policy(
        base_qx,
        adjusted_hrs,
        full_curve,
        effect_fraction,
        quality,
        discount,
        cost_discount,
        baseline_qalys_total,
    )
    life_years_gained = intervention_life_years - baseline_life_years

    (
        continuation_qaly_gains,
        continuation_life_years,
        continuation_cost_factor,
        continuation_qol_factor,
        continuation_survival,
        _continuation_qol_weights,
    ) = _simulate_reversible_policy(
        base_qx,
        adjusted_hrs,
        continuation_curve,
        effect_fraction,
        quality,
        discount,
        cost_discount,
        baseline_qalys_total,
    )
    continuation_life_years_gained = continuation_life_years - baseline_life_years

    (
        one_year_qaly_gains,
        one_year_life_years,
        one_year_cost_factor,
        one_year_qol_factor,
        one_year_survival,
        _one_year_qol_weights,
    ) = _simulate_reversible_policy(
        base_qx,
        adjusted_hrs,
        one_year_curve,
        effect_fraction,
        quality,
        discount,
        cost_discount,
        baseline_qalys_total,
    )
    one_year_life_years_gained = one_year_life_years - baseline_life_years

    # Common random numbers: one set of harm-parameter draws serves every view.
    direct_harms = _sample_harm_parameters(
        intervention.harm_model, harm_rng, n_simulations
    )
    interaction_harms = _sample_harm_parameters(
        _triggered_interaction_rules(intervention, active_interaction_tags),
        harm_rng,
        n_simulations,
    )

    def _view_harms(
        survival: np.ndarray, curve: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        return (
            _harm_draws_for_policy(
                direct_harms, survival, curve, discount, n_simulations
            ),
            _harm_draws_for_policy(
                interaction_harms, survival, curve, discount, n_simulations
            ),
        )

    direct_harm_draws, interaction_harm_draws = _view_harms(full_survival, full_curve)
    qaly_gains = qaly_gains + direct_harm_draws + interaction_harm_draws

    continuation_direct, continuation_interaction = _view_harms(
        continuation_survival, continuation_curve
    )
    continuation_qaly_gains = (
        continuation_qaly_gains + continuation_direct + continuation_interaction
    )

    one_year_direct, one_year_interaction = _view_harms(
        one_year_survival, one_year_curve
    )
    one_year_qaly_gains = one_year_qaly_gains + one_year_direct + one_year_interaction

    # Pathway contributions (approximate - using median HR)
    median_hr = np.median(adjusted_hrs)
    log_median = np.log(median_hr)
    cvd_contrib = (1 - np.exp(log_median * 1.3)) * np.mean(cause_fracs[:, 0])
    cancer_contrib = (1 - np.exp(log_median * 0.8)) * np.mean(cause_fracs[:, 1])
    other_contrib = (1 - np.exp(log_median * 0.6)) * np.mean(cause_fracs[:, 2])
    total_contrib = cvd_contrib + cancer_contrib + other_contrib
    if total_contrib > 0:
        cvd_contrib /= total_contrib
        cancer_contrib /= total_contrib
        other_contrib /= total_contrib

    # Posterior HR summaries (None when the intervention has no mortality arm).
    if has_direct_mortality_effect:
        posterior_hr_mean = float(np.mean(adjusted_hrs))
        posterior_hr_median = float(median_hr)
        posterior_hr_ci95 = (
            float(np.percentile(adjusted_hrs, 2.5)),
            float(np.percentile(adjusted_hrs, 97.5)),
        )
    else:
        posterior_hr_mean = None
        posterior_hr_median = None
        posterior_hr_ci95 = None

    result = _build_simulation_result(
        qaly_gains,
        cvd_contribution=float(cvd_contrib),
        cancer_contribution=float(cancer_contrib),
        other_contribution=float(other_contrib),
        life_years_gained=float(np.median(life_years_gained)),
        expected_discounted_cost_factor=expected_discounted_cost_factor,
        expected_qol_factor=expected_qol_factor,
        expected_qol_weights=tuple(float(weight) for weight in full_qol_weights),
        expected_harm_qalys=float(np.mean(direct_harm_draws)),
        expected_interaction_harm_qalys=float(np.mean(interaction_harm_draws)),
        annual_persistence=persistence,
        continuation_adjusted_mean=float(np.mean(continuation_qaly_gains)),
        continuation_adjusted_life_years_gained=float(
            np.median(continuation_life_years_gained)
        ),
        continuation_adjusted_cost_factor=continuation_cost_factor,
        continuation_adjusted_qol_factor=continuation_qol_factor,
        one_year_mean=float(np.mean(one_year_qaly_gains)),
        one_year_life_years_gained=float(np.median(one_year_life_years_gained)),
        one_year_cost_factor=one_year_cost_factor,
        one_year_qol_factor=one_year_qol_factor,
        causal_fraction_mean=causal_fraction_mean,
        causal_fraction_ci=causal_fraction_ci,
        posterior_hr_mean=posterior_hr_mean,
        posterior_hr_median=posterior_hr_median,
        posterior_hr_ci95=posterior_hr_ci95,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
        cost_discount_rate=cost_discount_rate,
    )
    if return_qaly_gains:
        return result, qaly_gains
    return result


def population_average_profile(
    age: int,
    sex: Literal["male", "female"],
) -> Profile:
    """Profile whose baseline mortality is the unadjusted life table.

    Normal BMI, never smoker, no diabetes or hypertension and moderate
    activity each carry relative risk 1.0, so the baseline mortality
    multiplier is exactly 1.0. :func:`simulate_qaly` uses this profile for
    its population-average baseline.
    """
    profile = Profile(
        age=age,
        sex=sex,
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="moderate",
    )
    multiplier = get_baseline_mortality_multiplier(profile)
    if multiplier != 1.0:
        raise RuntimeError(
            "population-average profile must have baseline mortality multiplier "
            f"1.0, got {multiplier!r}; the profile relative-risk tables changed"
        )
    return profile


def simulate_qaly(
    intervention: Intervention,
    age: int,
    sex: Literal["male", "female"],
    n_simulations: int = 10000,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    apply_confounding: bool = True,
    random_state: Optional[int] = None,
) -> SimulationResult:
    """
    Run Monte Carlo simulation to estimate QALY impact.

    Uses a population-average baseline: the unadjusted life table (see
    :func:`population_average_profile`) and no profile effect modifier. This is
    a thin wrapper over :func:`simulate_qaly_profile_vectorized`, so it returns
    exactly what that engine returns for the same inputs and seed.

    Args:
        intervention: Intervention to simulate
        age: Starting age
        sex: Biological sex for life table lookup
        n_simulations: Number of Monte Carlo iterations
        discount_rate: Annual discount rate (default 3% reference-case rate)
        apply_confounding: Whether to apply confounding adjustment
        random_state: Random seed for reproducibility

    Returns:
        SimulationResult with QALY estimates and uncertainty
    """
    return simulate_qaly_profile_vectorized(
        intervention,
        population_average_profile(age, sex),
        n_simulations=n_simulations,
        discount_rate=discount_rate,
        apply_confounding=apply_confounding,
        random_state=random_state,
        apply_intervention_modifier=False,
    )


def simulate_qaly_profile(
    intervention: Intervention,
    profile: Profile,
    n_simulations: int = 10000,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    apply_confounding: bool = True,
    random_state: Optional[int] = None,
    apply_intervention_modifier: bool = True,
) -> SimulationResult:
    """
    Run Monte Carlo simulation for a specific demographic profile.

    This extends simulate_qaly to incorporate profile-specific adjustments:
    1. Baseline mortality adjusted for BMI, smoking and activity level
    2. Intervention effect modified based on profile characteristics

    A thin wrapper over :func:`simulate_qaly_profile_vectorized`, so it returns
    exactly what that engine returns for the same inputs and seed.

    Args:
        intervention: Intervention to simulate
        profile: Demographic profile (age, sex, BMI, smoking, activity)
        n_simulations: Number of Monte Carlo iterations
        discount_rate: Annual discount rate (default 3% reference-case rate)
        apply_confounding: Whether to apply confounding adjustment
        random_state: Random seed for reproducibility
        apply_intervention_modifier: Whether to apply the profile's
            intervention effect modifier. Callers that have already baked it
            into the HR (e.g. the combined-intervention path) pass False.

    Returns:
        SimulationResult with QALY estimates and uncertainty
    """
    return simulate_qaly_profile_vectorized(
        intervention,
        profile,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
        apply_confounding=apply_confounding,
        random_state=random_state,
        apply_intervention_modifier=apply_intervention_modifier,
    )
