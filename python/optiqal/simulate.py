"""
Monte Carlo Simulation Module

Fast QALY estimation without full MCMC.
"""

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
)
from .lifecycle import LifecycleModel, PathwayHRs, get_mortality_rate, get_quality_weight, get_cause_fraction, QUALITY_WEIGHT_STD
from .confounding import adjust_hr
from .profile import Profile, get_baseline_mortality_multiplier, get_intervention_modifier


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
        ci95=(float(np.percentile(qaly_gains, 2.5)), float(np.percentile(qaly_gains, 97.5))),
        ci80=(float(np.percentile(qaly_gains, 10)), float(np.percentile(qaly_gains, 90))),
        ci50=(float(np.percentile(qaly_gains, 25)), float(np.percentile(qaly_gains, 75))),
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


def _zero_result(
    n_simulations: int,
    *,
    discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
) -> SimulationResult:
    """Return an exactly-null simulation result."""
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
        expected_discounted_cost_factor=1.0,
        expected_qol_factor=0.0,
        expected_qol_weights=(),
        expected_harm_qalys=0.0,
        expected_interaction_harm_qalys=0.0,
        annual_persistence=1.0,
        continuation_adjusted_mean=0.0,
        continuation_adjusted_life_years_gained=0.0,
        continuation_adjusted_cost_factor=1.0,
        continuation_adjusted_qol_factor=0.0,
        one_year_mean=0.0,
        one_year_life_years_gained=0.0,
        one_year_cost_factor=1.0,
        one_year_qol_factor=1.0,
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


def _simulate_reversible_policy(
    base_qx: np.ndarray,
    policy_hr: np.ndarray,
    continuation_curve: np.ndarray,
    quality: np.ndarray,
    qaly_discount: np.ndarray,
    cost_discount: np.ndarray,
    baseline_qalys_total: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float, float, np.ndarray, np.ndarray]:
    """Simulate a reversible intervention under an adherence policy.

    The all-cause hazard ratio ``policy_hr`` (one per simulation) is applied
    flat to baseline mortality, modulated by ``continuation_curve`` so the
    integrated survival effect exactly matches the sampled HR. The cause-
    specific pathway exponents are used only for the *reported* cvd/cancer/other
    decomposition (see below), never for this survival integration — applying
    them here attenuated every effect toward the null in an age-dependent way.
    """
    excess = (policy_hr - 1.0)[:, None]  # (n_simulations, 1)
    policy_multiplier = 1.0 + continuation_curve[None, :] * excess
    policy_qx = np.minimum(base_qx[None, :] * policy_multiplier, 0.99)

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
        np.sum(mean_policy_survival * continuation_curve * cost_discount)
    )
    policy_qol_factor = float(
        np.sum(mean_policy_survival * continuation_curve * qaly_discount)
    )
    policy_qol_weights = mean_policy_survival * continuation_curve * qaly_discount

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
    return dist.sample(
        n_simulations,
        random_state=int(rng.integers(0, np.iinfo(np.uint32).max)),
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
        if matches >= threshold and all(tag_counts[tag] > 0 for tag in rule.requires_tags):
            triggered.append(allocate_interaction_rule(rule, matches))

    return triggered


def _simulate_harm_draws(
    harm_sources: list[Union[HarmEffect, InteractionRule]],
    policy_survival: np.ndarray,
    continuation_curve: np.ndarray,
    qaly_discount: np.ndarray,
    rng: np.random.Generator,
    n_simulations: int,
) -> np.ndarray:
    """Sample direct or interaction harms on the same time grid as the benefit model."""
    if not harm_sources:
        return np.zeros(n_simulations)

    exposure_factor = np.sum(
        policy_survival * continuation_curve[None, :] * qaly_discount[None, :],
        axis=1,
    )
    harm_draws = np.zeros(n_simulations)

    for harm in harm_sources:
        if getattr(harm, "annual_qaly_loss", None) is not None:
            annual_qaly_loss = np.clip(
                _sample_distribution(harm.annual_qaly_loss, n_simulations, rng),
                0,
                None,
            )
            harm_draws -= annual_qaly_loss * exposure_factor

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
            annual_event_prob = np.clip(
                policy_survival * continuation_curve[None, :] * event_probability[:, None],
                0,
                1,
            )
            max_events = getattr(harm, "max_events", 1)
            if max_events == 1:
                lifetime_prob = 1 - np.prod(1 - annual_event_prob, axis=1)
                occurs = rng.random(n_simulations) < lifetime_prob
                harm_draws -= occurs * event_qaly_loss
            else:
                expected_events = np.sum(annual_event_prob, axis=1)
                event_counts = rng.poisson(expected_events)
                if max_events is not None:
                    event_counts = np.clip(event_counts, 0, max_events)
                harm_draws -= event_counts * event_qaly_loss

    return harm_draws


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
) -> Union[SimulationResult, tuple[SimulationResult, np.ndarray]]:
    """
    Vectorized Monte Carlo simulation - ~100x faster than loop version.

    Uses NumPy broadcasting to process all simulations at once.

    Args:
        discount_rate: Discount rate for QALYs (default 3% reference-case rate).
        cost_discount_rate: Discount rate for costs (default 3% reference-case rate).
        annual_persistence: Probability of renewing the intervention each year
            after the current year. Used to compute continuation-adjusted and
            one-year-only policy views for reversible interventions.
        active_years: Optional hard active-duration window for the primary policy.
            When provided, benefits, harms, and costs are only applied over this
            many years, with a prorated final year.
        return_qaly_gains: When true, also return the simulated net QALY draws.
    """
    discount_rate = validate_qaly_discount_rate(discount_rate)
    rng = np.random.default_rng(random_state)

    # Profile adjustments
    baseline_mortality_multiplier = get_baseline_mortality_multiplier(profile)
    intervention_effect_modifier = get_intervention_modifier(profile, intervention.category)

    # Pre-compute year arrays (static for all simulations)
    max_age = 100
    n_years = max_age - profile.age
    if n_years <= 0:
        # Profile age is at or beyond the modeled horizon, so there are no
        # remaining life-years to simulate. Return a null result instead of
        # crashing on empty/negative-length arrays below.
        zero = _zero_result(
            n_simulations,
            discount_rate=discount_rate,
            cost_discount_rate=cost_discount_rate,
        )
        return (zero, np.zeros(n_simulations)) if return_qaly_gains else zero
    years = np.arange(n_years)
    ages = profile.age + years

    # Base mortality rates, quality weights, discounts, cause fractions
    base_qx = np.array([get_mortality_rate(int(a), profile.sex) for a in ages])
    base_qx = np.minimum(
        base_qx * baseline_mortality_multiplier * float(max(baseline_hazard_multiplier, 0.0)),
        0.99,
    )
    base_quality = np.array([get_quality_weight(int(a)) for a in ages])
    discount = (1 / (1 + discount_rate)) ** years
    cost_discount = (1 / (1 + cost_discount_rate)) ** years

    # Cause fractions (n_years, 3)
    cause_fracs = np.array([[get_cause_fraction(int(a))[k] for k in ['cvd', 'cancer', 'other']] for a in ages])

    # Sample quality weight offsets (MEPS calibration: within-age σ=0.117)
    # Each simulation gets a person-specific offset that persists across years
    quality_offsets = rng.normal(0, QUALITY_WEIGHT_STD, n_simulations)  # (n_simulations,)
    # Quality weights vary by simulation: (n_simulations, n_years)
    quality = np.clip(base_quality[None, :] + quality_offsets[:, None], 0.1, 1.0)

    # Sample HRs and causal fractions (n_simulations,)
    if intervention.mortality is not None:
        hr_samples = intervention.mortality.hazard_ratio.sample(n_simulations, random_state)

        if intervention_effect_modifier != 1.0:
            hr_samples = np.exp(np.log(hr_samples) * intervention_effect_modifier)

        if apply_confounding and intervention.confounding_prior is not None:
            causal_samples = intervention.confounding_prior.sample(n_simulations, random_state)
            causal_fraction_mean = intervention.confounding_prior.mean
            causal_fraction_ci = intervention.confounding_prior.ci(0.95)
        else:
            causal_samples = np.ones(n_simulations)
            causal_fraction_mean = None
            causal_fraction_ci = None

        # Adjust HRs for confounding: log(adjusted_hr) = causal_fraction * log(observed_hr)
        # Adjust HRs for confounding: log(adjusted_hr) = causal_fraction * log(observed_hr).
        # This all-cause HR is applied flat to mortality (see _simulate_reversible_policy);
        # the 1.3/0.8/0.6 pathway exponents below feed only the reported decomposition.
        adjusted_hrs = np.exp(causal_samples * np.log(hr_samples))  # (n_simulations,)
        if global_intervention_hr_multiplier != 1.0:
            adjusted_hrs = np.clip(adjusted_hrs * global_intervention_hr_multiplier, 1e-6, None)
    else:
        adjusted_hrs = np.full(n_simulations, max(global_intervention_hr_multiplier, 1e-6))
        causal_fraction_mean = None
        causal_fraction_ci = None

    # Baseline survival (deterministic, same for all simulations)
    baseline_survival = np.cumprod(1 - base_qx)
    baseline_survival = np.concatenate([[1.0], baseline_survival[:-1]])  # Shift for start-of-year
    baseline_life_years = np.sum(baseline_survival)

    # Baseline QALYs now vary by simulation due to quality weight heterogeneity
    # baseline_qalys_per_year: (n_simulations, n_years)
    baseline_qalys_per_year = baseline_survival[None, :] * quality * discount[None, :]
    baseline_qalys_total = np.sum(baseline_qalys_per_year, axis=1)  # (n_simulations,)

    full_curve = _active_years_curve(n_years, active_years)
    persistence = float(np.clip(annual_persistence, 0.0, 1.0))
    continuation_curve = full_curve * (persistence ** years)
    one_year_curve = np.zeros(n_years)
    one_year_curve[0] = 1.0

    (
        qaly_gains,
        intervention_life_years,
        expected_discounted_cost_factor,
        expected_qol_factor,
        full_survival,
        full_qol_weights,
    ) = (
        _simulate_reversible_policy(
            base_qx,
            adjusted_hrs,
            full_curve,
            quality,
            discount,
            cost_discount,
            baseline_qalys_total,
        )
    )
    life_years_gained = intervention_life_years - baseline_life_years

    (
        continuation_qaly_gains,
        continuation_life_years,
        continuation_cost_factor,
        continuation_qol_factor,
        continuation_survival,
        _continuation_qol_weights,
    ) = (
        _simulate_reversible_policy(
            base_qx,
            adjusted_hrs,
            continuation_curve,
            quality,
            discount,
            cost_discount,
            baseline_qalys_total,
        )
    )
    continuation_life_years_gained = continuation_life_years - baseline_life_years

    (
        one_year_qaly_gains,
        one_year_life_years,
        one_year_cost_factor,
        one_year_qol_factor,
        one_year_survival,
        _one_year_qol_weights,
    ) = (
        _simulate_reversible_policy(
            base_qx,
            adjusted_hrs,
            one_year_curve,
            quality,
            discount,
            cost_discount,
            baseline_qalys_total,
        )
    )
    one_year_life_years_gained = one_year_life_years - baseline_life_years

    direct_harm_draws = _simulate_harm_draws(
        intervention.harm_model,
        full_survival,
        full_curve,
        discount,
        rng,
        n_simulations,
    )
    interaction_harm_draws = _simulate_harm_draws(
        _triggered_interaction_rules(intervention, active_interaction_tags),
        full_survival,
        full_curve,
        discount,
        rng,
        n_simulations,
    )
    qaly_gains = qaly_gains + direct_harm_draws + interaction_harm_draws

    continuation_qaly_gains = continuation_qaly_gains + _simulate_harm_draws(
        intervention.harm_model,
        continuation_survival,
        continuation_curve,
        discount,
        rng,
        n_simulations,
    ) + _simulate_harm_draws(
        _triggered_interaction_rules(intervention, active_interaction_tags),
        continuation_survival,
        continuation_curve,
        discount,
        rng,
        n_simulations,
    )

    one_year_qaly_gains = one_year_qaly_gains + _simulate_harm_draws(
        intervention.harm_model,
        one_year_survival,
        one_year_curve,
        discount,
        rng,
        n_simulations,
    ) + _simulate_harm_draws(
        _triggered_interaction_rules(intervention, active_interaction_tags),
        one_year_survival,
        one_year_curve,
        discount,
        rng,
        n_simulations,
    )

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
    if intervention.mortality is not None:
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
    discount_rate = validate_qaly_discount_rate(discount_rate)
    if intervention.mortality is None:
        return _zero_result(n_simulations, discount_rate=discount_rate)

    # Sample from distributions
    hr_samples = intervention.mortality.hazard_ratio.sample(n_simulations, random_state)

    # Sample causal fractions if applying confounding
    if apply_confounding and intervention.confounding_prior is not None:
        causal_samples = intervention.confounding_prior.sample(n_simulations, random_state)
        causal_fraction_mean = intervention.confounding_prior.mean
        causal_fraction_ci = intervention.confounding_prior.ci(0.95)
    else:
        causal_samples = np.ones(n_simulations)
        causal_fraction_mean = None
        causal_fraction_ci = None

    # Run lifecycle calculations
    qaly_gains = np.zeros(n_simulations)
    life_years = np.zeros(n_simulations)
    cvd_contributions = np.zeros(n_simulations)
    cancer_contributions = np.zeros(n_simulations)
    other_contributions = np.zeros(n_simulations)

    lifecycle = LifecycleModel(
        start_age=age,
        sex=sex,
        discount_rate=discount_rate,
    )

    # Base HR for pathway distribution
    base_hr = intervention.mortality.hazard_ratio.mean

    for i in range(n_simulations):
        # Sample HR and causal fraction
        sampled_hr = hr_samples[i]
        causal_fraction = causal_samples[i]

        # Adjust HR for confounding
        adjusted_hr = adjust_hr(sampled_hr, causal_fraction)

        # Convert to pathway HRs
        log_hr = np.log(adjusted_hr)
        pathway_hrs = PathwayHRs(
            cvd=np.exp(log_hr * 1.3),  # CVD gets stronger effect
            cancer=np.exp(log_hr * 0.8),
            other=np.exp(log_hr * 0.6),
        )

        # Run lifecycle calculation
        result = lifecycle.calculate(pathway_hrs)

        qaly_gains[i] = result.qaly_gain
        life_years[i] = result.life_years_gained
        cvd_contributions[i] = result.pathway_contributions["cvd"]
        cancer_contributions[i] = result.pathway_contributions["cancer"]
        other_contributions[i] = result.pathway_contributions["other"]

    return _build_simulation_result(
        qaly_gains,
        cvd_contribution=float(np.median(cvd_contributions)),
        cancer_contribution=float(np.median(cancer_contributions)),
        other_contribution=float(np.median(other_contributions)),
        life_years_gained=float(np.median(life_years)),
        causal_fraction_mean=causal_fraction_mean,
        causal_fraction_ci=causal_fraction_ci,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
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
    1. Baseline mortality adjusted for BMI, smoking, diabetes
    2. Intervention effect modified based on profile characteristics

    Args:
        intervention: Intervention to simulate
        profile: Demographic profile (age, sex, BMI, smoking, diabetes)
        n_simulations: Number of Monte Carlo iterations
        discount_rate: Annual discount rate (default 3% reference-case rate)
        apply_confounding: Whether to apply confounding adjustment
        random_state: Random seed for reproducibility

    Returns:
        SimulationResult with QALY estimates and uncertainty
    """
    discount_rate = validate_qaly_discount_rate(discount_rate)
    if intervention.mortality is None:
        return _zero_result(n_simulations, discount_rate=discount_rate)

    # Get profile-specific adjustments
    baseline_mortality_multiplier = get_baseline_mortality_multiplier(profile)
    # Callers that have already baked the profile modifier into the HR (e.g. the
    # combined-intervention path) pass apply_intervention_modifier=False to avoid
    # double-counting it.
    intervention_effect_modifier = (
        get_intervention_modifier(profile, intervention.category)
        if apply_intervention_modifier
        else 1.0
    )

    # Sample from distributions
    hr_samples = intervention.mortality.hazard_ratio.sample(n_simulations, random_state)

    # Apply intervention effect modifier
    # If modifier > 1, intervention is more effective (HR moves further from 1)
    # log(adjusted_hr) = log(hr) * modifier (for HR < 1)
    if intervention_effect_modifier != 1.0:
        log_hr = np.log(hr_samples)
        hr_samples = np.exp(log_hr * intervention_effect_modifier)

    # Sample causal fractions if applying confounding
    if apply_confounding and intervention.confounding_prior is not None:
        causal_samples = intervention.confounding_prior.sample(n_simulations, random_state)
        causal_fraction_mean = intervention.confounding_prior.mean
        causal_fraction_ci = intervention.confounding_prior.ci(0.95)
    else:
        causal_samples = np.ones(n_simulations)
        causal_fraction_mean = None
        causal_fraction_ci = None

    # Run lifecycle calculations
    qaly_gains = np.zeros(n_simulations)
    life_years = np.zeros(n_simulations)
    cvd_contributions = np.zeros(n_simulations)
    cancer_contributions = np.zeros(n_simulations)
    other_contributions = np.zeros(n_simulations)

    lifecycle = LifecycleModel(
        start_age=profile.age,
        sex=profile.sex,
        discount_rate=discount_rate,
        baseline_mortality_multiplier=baseline_mortality_multiplier,
    )

    for i in range(n_simulations):
        sampled_hr = hr_samples[i]
        causal_fraction = causal_samples[i]

        # Adjust HR for confounding
        adjusted_hr = adjust_hr(sampled_hr, causal_fraction)

        # Convert to pathway HRs
        log_hr = np.log(adjusted_hr)
        pathway_hrs = PathwayHRs(
            cvd=np.exp(log_hr * 1.3),
            cancer=np.exp(log_hr * 0.8),
            other=np.exp(log_hr * 0.6),
        )

        result = lifecycle.calculate(pathway_hrs)

        qaly_gains[i] = result.qaly_gain
        life_years[i] = result.life_years_gained
        cvd_contributions[i] = result.pathway_contributions["cvd"]
        cancer_contributions[i] = result.pathway_contributions["cancer"]
        other_contributions[i] = result.pathway_contributions["other"]

    return _build_simulation_result(
        qaly_gains,
        cvd_contribution=float(np.median(cvd_contributions)),
        cancer_contribution=float(np.median(cancer_contributions)),
        other_contribution=float(np.median(other_contributions)),
        life_years_gained=float(np.median(life_years)),
        causal_fraction_mean=causal_fraction_mean,
        causal_fraction_ci=causal_fraction_ci,
        n_simulations=n_simulations,
        discount_rate=discount_rate,
    )
