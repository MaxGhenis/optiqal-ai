"""Property and regression tests for the simulation engine's invariants.

The properties check the engine against oracles written in this file: a
from-scratch start-of-year survival recurrence, SciPy quadrature of the
declared onset/ramp/decay profile, and exhaustive enumeration of every
alive/dead and event/no-event path. The oracles take only data from the
package (life-table rates, quality weights, relative-risk tables), so an error
shared by the engine and its own helpers cannot cancel. The regression cases
are the minimized counterexamples from the 2026-09-25 invariants audit, with
the audited (wrong) value noted beside each.
"""

from __future__ import annotations

import itertools
import math
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.integrate import quad

import optiqal.simulate as simulate
from optiqal.catalog import CATALOG
from optiqal.combination import simulate_combined_qaly
from optiqal.confounding import ConfoundingPrior
from optiqal.intervention import (
    Distribution,
    HarmEffect,
    InteractionRule,
    Intervention,
    MortalityEffect,
)
from optiqal.lifecycle import get_mortality_rate, get_quality_weight
from optiqal.profile import (
    ACTIVITY_MORTALITY_RR,
    BMI_MORTALITY_RR,
    SMOKING_MORTALITY_RR,
    Profile,
)
from optiqal.simulate import (
    _simulate_harm_draws,
    _simulate_reversible_policy,
    expected_event_loss,
    mortality_effect_fraction,
    population_average_profile,
    simulate_qaly,
    simulate_qaly_profile,
    simulate_qaly_profile_vectorized,
)
from optiqal.stack_interactions import expected_stack_interaction_qaly

MAX_AGE = 100  # the engine's modeled horizon
PROPERTY_SETTINGS = dict(deadline=None, database=None, derandomize=True)

# ---------------------------------------------------------------------------
# Helpers and independent oracles
# ---------------------------------------------------------------------------


def point(value: float) -> Distribution:
    return Distribution(type="point", params={"value": value})


def make_profile(
    age: int = 40,
    sex: str = "male",
    *,
    high_risk: bool = False,
) -> Profile:
    return Profile(
        age=age,
        sex=sex,
        bmi_category="severely_obese" if high_risk else "normal",
        smoking_status="current" if high_risk else "never",
        has_diabetes=False,
        activity_level="sedentary" if high_risk else "moderate",
    )


def make_item(
    hr: Optional[float] = 0.8,
    *,
    onset: float = 0.0,
    ramp: float = 0.0,
    decay: float = 0.0,
    harms: tuple = (),
    tags: tuple = (),
    rules: tuple = (),
    item_id: str = "audit",
) -> Intervention:
    mortality = None
    if hr is not None:
        mortality = MortalityEffect(
            point(hr), onset_delay=onset, ramp_up=ramp, decay_rate=decay
        )
    return Intervention(
        id=item_id,
        name=item_id,
        category="other",
        mortality=mortality,
        harm_model=list(harms),
        interaction_tags=list(tags),
        interaction_rules=list(rules),
    )


@contextmanager
def quality_noise_disabled():
    """Remove only the per-draw quality offsets, where the engine reads them."""
    original = simulate.QUALITY_WEIGHT_STD
    simulate.QUALITY_WEIGHT_STD = 0.0
    try:
        yield
    finally:
        simulate.QUALITY_WEIGHT_STD = original


def table_multiplier(profile: Profile) -> float:
    """Baseline mortality multiplier straight from the relative-risk tables."""
    return (
        BMI_MORTALITY_RR[profile.bmi_category]
        * SMOKING_MORTALITY_RR[profile.smoking_status]
        * ACTIVITY_MORTALITY_RR[profile.activity_level]
    )


def reference_path(
    profile: Profile,
    hazard_multipliers,
    *,
    discount_rate: float = 0.03,
    baseline_hazard_multiplier: float = 1.0,
) -> tuple[float, float, list[float]]:
    """Discounted QALYs, life-years and survival by a plain start-of-year loop.

    ``S[0] = 1`` and ``S[t+1] = S[t] * (1 - min(q_t * m_t, 0.99))``, where
    ``q_t = min(qx(age_t) * rr, 0.99)`` is the profile's capped baseline
    mortality (the HR scales the probability the person actually faces) and
    ``m_t`` is the year's hazard multiplier. QALYs are
    ``sum_t S[t] * Q(age_t) * (1 + r)**-t``.
    """
    rr = table_multiplier(profile) * max(baseline_hazard_multiplier, 0.0)
    alive = 1.0
    qalys = 0.0
    life_years = 0.0
    survival = []
    for t in range(MAX_AGE - profile.age):
        age = profile.age + t
        q = min(get_mortality_rate(age, profile.sex) * rr, 0.99)
        survival.append(alive)
        qalys += alive * get_quality_weight(age) * (1.0 + discount_rate) ** -t
        life_years += alive
        alive *= 1.0 - min(q * hazard_multipliers[t], 0.99)
    return qalys, life_years, survival


def reference_effect_fraction(n_years, onset, ramp, decay) -> np.ndarray:
    """Year averages of the declared effect profile by adaptive quadrature."""

    def share(tau: float) -> float:
        if tau < onset:
            return 0.0
        since = tau - onset
        ramped = min(1.0, since / ramp) if ramp > 0 else 1.0
        return ramped * math.exp(-decay * since)

    fractions = []
    for t in range(n_years):
        kinks = [x for x in (onset, onset + ramp) if t < x < t + 1]
        value, _ = quad(
            share, t, t + 1, points=kinks or None, epsabs=1e-14, epsrel=1e-13
        )
        fractions.append(value)
    return np.array(fractions)


def reference_active_curve(n_years, active_years, persistence=1.0) -> np.ndarray:
    """Share of each year on the intervention: whole years, then a remainder."""
    if active_years is None:
        curve = np.ones(n_years)
    else:
        curve = np.clip(active_years - np.arange(n_years), 0.0, 1.0)
    return curve * persistence ** np.arange(n_years)


def enumerate_event_loss(survival, exposure, discount, p, loss, max_events):
    """Expected counted event loss by summing over every path.

    A path is how many years the person starts alive (``k``, with probability
    ``S[k-1] - S[k]``) and, for each of those years, whether the event happens
    (chance ``exposure[t] * p``). Only the first ``max_events`` events count.
    """
    n_years = len(survival)
    alive_start = [1.0, *survival, 0.0]  # S[-1] = 1, S[n] = 0
    total = 0.0
    for years_alive in range(n_years + 1):
        path_probability = alive_start[years_alive] - alive_start[years_alive + 1]
        if path_probability == 0.0:
            continue
        for events in itertools.product((0, 1), repeat=years_alive):
            probability = path_probability
            counted = 0
            path_loss = 0.0
            for t, happened in enumerate(events):
                chance = exposure[t] * p
                probability *= chance if happened else 1.0 - chance
                if happened:
                    if max_events is None or counted < max_events:
                        path_loss += loss * discount[t]
                    counted += 1
            total += probability * path_loss
    return total


def draws(intervention, profile, **kwargs):
    kwargs.setdefault("n_simulations", 16)
    kwargs.setdefault("random_state", 0)
    return simulate_qaly_profile_vectorized(
        intervention, profile, return_qaly_gains=True, **kwargs
    )


profiles = st.builds(
    Profile,
    age=st.integers(0, 99),
    sex=st.sampled_from(["male", "female"]),
    bmi_category=st.sampled_from(sorted(BMI_MORTALITY_RR)),
    smoking_status=st.sampled_from(sorted(SMOKING_MORTALITY_RR)),
    has_diabetes=st.booleans(),
    has_hypertension=st.booleans(),
    activity_level=st.sampled_from(sorted(ACTIVITY_MORTALITY_RR)),
)
discount_rates = st.sampled_from([0.0, 0.03, 0.1])
baseline_hazard_multipliers = st.sampled_from([1.0, 0.8, 1.08, 2.5])


# ---------------------------------------------------------------------------
# One integrator: wrappers, the vectorized engine and the oracle agree
# ---------------------------------------------------------------------------


@settings(max_examples=80, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    hr=st.floats(0.05, 3.0),
    discount_rate=discount_rates,
    baseline_hazard_multiplier=baseline_hazard_multipliers,
)
def test_engine_matches_independent_recurrence(
    profile, hr, discount_rate, baseline_hazard_multiplier
):
    n_years = MAX_AGE - profile.age
    with quality_noise_disabled():
        result, gains = draws(
            make_item(hr),
            profile,
            n_simulations=3,
            discount_rate=discount_rate,
            baseline_hazard_multiplier=baseline_hazard_multiplier,
            apply_confounding=False,
        )
    kwargs = dict(
        discount_rate=discount_rate,
        baseline_hazard_multiplier=baseline_hazard_multiplier,
    )
    base_qalys, base_years, _ = reference_path(profile, np.ones(n_years), **kwargs)
    policy_qalys, policy_years, _ = reference_path(
        profile, np.full(n_years, hr), **kwargs
    )
    expected = policy_qalys - base_qalys
    for gain in gains:
        assert math.isclose(gain, expected, rel_tol=1e-12, abs_tol=1e-11)
    assert math.isclose(
        result.life_years_gained,
        policy_years - base_years,
        rel_tol=1e-12,
        abs_tol=1e-11,
    )


@settings(max_examples=60, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    hr=st.floats(0.05, 3.0),
    onset=st.floats(0.0, 30.0),
    ramp=st.floats(0.0, 10.0),
    decay=st.sampled_from([0.0, 0.02, 0.3]),
    active_years=st.one_of(st.none(), st.floats(0.0, 40.0)),
    persistence=st.floats(0.0, 1.0),
    discount_rate=discount_rates,
)
def test_engine_views_match_oracle_with_declared_timing(
    profile, hr, onset, ramp, decay, active_years, persistence, discount_rate
):
    n_years = MAX_AGE - profile.age
    item = make_item(hr, onset=onset, ramp=ramp, decay=decay)
    with quality_noise_disabled():
        result = simulate_qaly_profile_vectorized(
            item,
            profile,
            n_simulations=1,
            discount_rate=discount_rate,
            cost_discount_rate=discount_rate,
            annual_persistence=persistence,
            active_years=active_years,
            apply_confounding=False,
            random_state=0,
        )
    fraction = reference_effect_fraction(n_years, onset, ramp, decay)
    base_qalys, _, _ = reference_path(
        profile, np.ones(n_years), discount_rate=discount_rate
    )
    one_year = np.zeros(n_years)
    one_year[0] = 1.0
    views = {
        "mean": reference_active_curve(n_years, active_years),
        "continuation_adjusted_mean": reference_active_curve(
            n_years, active_years, persistence
        ),
        "one_year_mean": one_year,
    }
    for field, exposure in views.items():
        multipliers = 1.0 + exposure * fraction * (hr - 1.0)
        policy_qalys, _, survival = reference_path(
            profile, multipliers, discount_rate=discount_rate
        )
        assert math.isclose(
            getattr(result, field), policy_qalys - base_qalys, abs_tol=1e-9
        ), field
        if field == "mean":
            # Costs and utility exposure follow adherence, not the onset.
            discount = (1.0 + discount_rate) ** -np.arange(n_years)
            exposure_factor = float(np.sum(np.array(survival) * exposure * discount))
            assert math.isclose(
                result.expected_discounted_cost_factor, exposure_factor, abs_tol=1e-9
            )
            assert math.isclose(
                result.expected_qol_factor, exposure_factor, abs_tol=1e-9
            )


def uncertain_items():
    harms = st.lists(
        st.builds(
            HarmEffect,
            id=st.sampled_from(["h1", "h2"]),
            annual_qaly_loss=st.one_of(
                st.none(),
                st.builds(
                    lambda low, width: Distribution(
                        "uniform", {"min": low, "max": low + width}
                    ),
                    st.floats(0.0, 0.01),
                    st.floats(0.0, 0.01),
                ),
            ),
            event_probability=st.one_of(st.none(), st.floats(0.0, 0.3).map(point)),
            event_qaly_loss=st.floats(0.0, 0.5).map(point),
            max_events=st.sampled_from([1, 2, None]),
        ),
        max_size=2,
    )
    return st.builds(
        lambda hr, log_sd, category, prior, harm_model, onset: Intervention(
            id="uncertain",
            name="Uncertain",
            category=category,
            mortality=MortalityEffect(
                Distribution("lognormal", {"hr": hr, "log_sd": log_sd}),
                onset_delay=onset,
            ),
            harm_model=harm_model,
            confounding_prior=prior,
        ),
        st.floats(0.3, 2.0),
        st.floats(0.0, 0.5),
        st.sampled_from(["exercise", "diet", "smoking", "sleep", "other"]),
        st.one_of(st.none(), st.just(ConfoundingPrior(alpha=2.5, beta=5.0))),
        harms,
        st.sampled_from([0.0, 1.5]),
    )


@settings(max_examples=40, **PROPERTY_SETTINGS)
@given(
    item=uncertain_items(),
    profile=profiles,
    seed=st.integers(0, 2**16),
    n_simulations=st.sampled_from([1, 16, 64]),
    discount_rate=discount_rates,
    apply_confounding=st.booleans(),
    apply_modifier=st.booleans(),
)
def test_public_wrappers_return_the_vectorized_result_field_for_field(
    item, profile, seed, n_simulations, discount_rate, apply_confounding, apply_modifier
):
    common = dict(
        n_simulations=n_simulations,
        discount_rate=discount_rate,
        apply_confounding=apply_confounding,
        random_state=seed,
    )
    assert asdict(
        simulate_qaly_profile(
            item, profile, apply_intervention_modifier=apply_modifier, **common
        )
    ) == asdict(
        simulate_qaly_profile_vectorized(
            item, profile, apply_intervention_modifier=apply_modifier, **common
        )
    )
    assert asdict(simulate_qaly(item, profile.age, profile.sex, **common)) == asdict(
        simulate_qaly_profile_vectorized(
            item,
            population_average_profile(profile.age, profile.sex),
            apply_intervention_modifier=False,
            **common,
        )
    )


SCALAR_VECTOR_CASES = [
    # (age, sex, hr, audited scalar value where the audit recorded one)
    (40, "male", 0.8, 0.580388223690651),
    (20, "female", 1.2, -0.2629746958726642),
    (90, "male", 0.0001, 3.058797176716233),
    *[
        (age, sex, hr, None)
        for age, sex, hr in itertools.product(
            (40, 80), ("male", "female"), (0.5, 0.8, 1.0)
        )
    ],
]


@pytest.mark.parametrize("age,sex,hr,audited_scalar", SCALAR_VECTOR_CASES)
def test_audit_scalar_and_vector_engines_agree(age, sex, hr, audited_scalar):
    """Audit: HR .8 at 40 gave scalar 0.5804 against vector 0.6604 QALYs."""
    profile = make_profile(age, sex)
    with quality_noise_disabled():
        scalar = simulate_qaly_profile(
            make_item(hr), profile, n_simulations=1, random_state=0
        )
        vector = simulate_qaly_profile_vectorized(
            make_item(hr), profile, n_simulations=1, random_state=0
        )
    n_years = MAX_AGE - age
    base, _, _ = reference_path(profile, np.ones(n_years))
    policy, _, _ = reference_path(profile, np.full(n_years, hr))
    assert scalar.mean == vector.mean
    assert math.isclose(vector.mean, policy - base, rel_tol=1e-12, abs_tol=1e-11)
    if audited_scalar is not None:
        assert not math.isclose(scalar.mean, audited_scalar, abs_tol=1e-3)
    if (age, sex, hr) == (40, "male", 0.8):
        assert vector.mean == pytest.approx(0.6604002678252101, abs=1e-12)


def test_simulate_qaly_counts_harms_and_cost_exposure_without_a_mortality_arm():
    """The old loop returned a hardcoded null (cost factor 1, no harms) here."""
    harm = HarmEffect("sedation", annual_qaly_loss=point(0.01))
    result = simulate_qaly(
        make_item(None, harms=(harm,)), 40, "male", n_simulations=8, random_state=0
    )
    _, _, survival = reference_path(make_profile(40), np.ones(MAX_AGE - 40))
    exposure = float(np.sum(np.array(survival) * 1.03 ** -np.arange(MAX_AGE - 40)))
    assert result.expected_harm_qalys == pytest.approx(-0.01 * exposure, rel=1e-12)
    assert result.mean == pytest.approx(result.expected_harm_qalys, rel=1e-12)
    assert result.expected_discounted_cost_factor == pytest.approx(exposure, rel=1e-12)


def test_population_average_profile_has_unit_baseline_multiplier(monkeypatch):
    for sex in ("male", "female"):
        assert table_multiplier(population_average_profile(40, sex)) == 1.0
    monkeypatch.setitem(ACTIVITY_MORTALITY_RR, "moderate", 1.1)
    with pytest.raises(RuntimeError, match="multiplier"):
        population_average_profile(40, "male")


def test_simulate_qaly_skips_the_profile_effect_modifier():
    """An exercise item keeps its HR: the moderate-activity modifier (0.6) is off."""
    item = make_item(0.8)
    item.category = "exercise"
    with quality_noise_disabled():
        result = simulate_qaly(item, 40, "male", n_simulations=1, random_state=0)
    base, _, _ = reference_path(make_profile(40), np.ones(MAX_AGE - 40))
    policy, _, _ = reference_path(make_profile(40), np.full(MAX_AGE - 40, 0.8))
    assert result.mean == pytest.approx(policy - base, rel=1e-12)


# ---------------------------------------------------------------------------
# Declared onset, ramp-up and decay
# ---------------------------------------------------------------------------


ONSET_CASES = [
    # (age, sex, hr, onset, audited gain)
    (98, "male", 0.5, 2.0, 0.10768041015908603),
    (18, "female", 0.2, 82.0, 1.5651690446457451),
    (80, "male", 0.9, 20.0, 0.3177751747519572),
    *[
        (age, sex, hr, float(MAX_AGE - age + after), None)
        for age, sex, hr, after in itertools.product(
            (98, 99), ("male", "female"), (0.5, 0.8), (0, 1)
        )
    ],
]


@pytest.mark.parametrize("age,sex,hr,onset,audited_gain", ONSET_CASES)
def test_audit_no_mortality_benefit_before_declared_onset(
    age, sex, hr, onset, audited_gain
):
    result = simulate_qaly_profile_vectorized(
        make_item(hr, onset=onset),
        make_profile(age, sex),
        n_simulations=1,
        random_state=0,
    )
    assert result.mean == 0.0
    assert result.life_years_gained == 0.0
    assert result.continuation_adjusted_mean == 0.0
    assert result.one_year_mean == 0.0


@settings(max_examples=60, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    hr=st.floats(0.01, 50.0),
    onset_beyond=st.floats(0.0, 20.0),
    ramp=st.floats(0.0, 5.0),
    decay=st.floats(0.0, 1.0),
    persistence=st.floats(0.0, 1.0),
    active_years=st.one_of(st.none(), st.floats(0.0, 120.0)),
)
def test_onset_at_or_after_the_horizon_leaves_mortality_exactly_null(
    profile, hr, onset_beyond, ramp, decay, persistence, active_years
):
    onset = MAX_AGE - profile.age + onset_beyond
    result, gains = draws(
        make_item(hr, onset=onset, ramp=ramp, decay=decay),
        profile,
        annual_persistence=persistence,
        active_years=active_years,
    )
    assert np.all(gains == 0.0)
    assert result.life_years_gained == 0.0
    assert result.continuation_adjusted_mean == 0.0
    assert result.one_year_mean == 0.0


@settings(max_examples=40, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    hr=st.floats(0.05, 20.0),
    onsets=st.lists(st.floats(0.0, 40.0), min_size=2, max_size=2).map(sorted),
    ramp=st.floats(0.0, 5.0),
    seed=st.integers(0, 2**16),
)
def test_later_onset_never_increases_the_mortality_effect(
    profile, hr, onsets, ramp, seed
):
    """Protective gains and harmful losses both shrink as onset moves later.

    Holds without decay; with decay a later onset also starts the fade later,
    so no monotonicity is claimed there.
    """
    _, early = draws(
        make_item(hr, onset=onsets[0], ramp=ramp), profile, random_state=seed
    )
    _, late = draws(
        make_item(hr, onset=onsets[1], ramp=ramp), profile, random_state=seed
    )
    if hr <= 1.0:
        assert np.all(late <= early + 1e-12)
        assert np.all(late >= -1e-12)
    else:
        assert np.all(late >= early - 1e-12)
        assert np.all(late <= 1e-12)


@settings(max_examples=40, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    hr=st.floats(0.05, 1.0),
    ramps=st.lists(st.floats(0.0, 20.0), min_size=2, max_size=2).map(sorted),
    onset=st.floats(0.0, 5.0),
    decay=st.sampled_from([0.0, 0.05, 0.5]),
    seed=st.integers(0, 2**16),
)
def test_slower_ramp_never_increases_a_protective_gain(
    profile, hr, ramps, onset, decay, seed
):
    _, fast = draws(
        make_item(hr, onset=onset, ramp=ramps[0], decay=decay),
        profile,
        random_state=seed,
    )
    _, slow = draws(
        make_item(hr, onset=onset, ramp=ramps[1], decay=decay),
        profile,
        random_state=seed,
    )
    assert np.all(slow <= fast + 1e-12)


@settings(max_examples=150, **PROPERTY_SETTINGS)
@given(
    n_years=st.integers(1, 12),
    onset=st.floats(0.0, 10.0),
    ramp=st.floats(0.0, 6.0),
    decay=st.one_of(st.just(0.0), st.floats(1e-9, 1e-3), st.floats(1e-3, 5.0)),
)
def test_effect_fraction_is_the_exact_year_average(n_years, onset, ramp, decay):
    fraction = mortality_effect_fraction(n_years, onset, ramp, decay)
    assert np.all((fraction >= 0.0) & (fraction <= 1.0))
    np.testing.assert_allclose(
        fraction,
        reference_effect_fraction(n_years, onset, ramp, decay),
        rtol=0,
        atol=1e-10,
    )


def test_no_declared_timing_is_exactly_the_immediate_effect():
    assert np.array_equal(mortality_effect_fraction(100), np.ones(100))
    assert np.array_equal(mortality_effect_fraction(7, 0, 0, 0), np.ones(7))
    immediate = MortalityEffect(point(0.8))
    assert (immediate.onset_delay, immediate.ramp_up, immediate.decay_rate) == (0, 0, 0)
    declared_zero = make_item(0.8, onset=0.0, ramp=0.0, decay=0.0)
    default = Intervention("audit", "audit", "other", mortality=immediate)
    profile = make_profile(40)
    assert asdict(
        simulate_qaly_profile_vectorized(
            declared_zero, profile, n_simulations=16, random_state=3
        )
    ) == asdict(
        simulate_qaly_profile_vectorized(
            default, profile, n_simulations=16, random_state=3
        )
    )


def test_catalog_interventions_declare_no_timing():
    """The web path builds MortalityEffect without timing, so onset cannot move it."""
    for entry in CATALOG.values():
        mortality = entry.to_intervention().mortality
        if mortality is None:
            continue
        assert (mortality.onset_delay, mortality.ramp_up, mortality.decay_rate) == (
            0,
            0,
            0,
        ), entry.id


@pytest.mark.parametrize("bad", [-0.5, float("nan"), float("inf"), None, "soon"])
def test_timing_parameters_must_be_finite_and_nonnegative(bad):
    for field in ("onset_delay", "ramp_up", "decay_rate"):
        with pytest.raises(ValueError, match=field):
            MortalityEffect(point(0.8), **{field: bad})
    with pytest.raises(ValueError):
        mortality_effect_fraction(5, onset_delay=bad)


# ---------------------------------------------------------------------------
# Event harms: first-event accounting, caps and discounting
# ---------------------------------------------------------------------------


@st.composite
def event_cases(draw):
    n_years = draw(st.integers(1, 4))
    n_draws = draw(st.integers(1, 3))
    unit = st.floats(0.0, 1.0)
    rows = []
    for _ in range(n_draws):
        steps = draw(st.lists(unit, min_size=n_years, max_size=n_years))
        if draw(st.booleans()):
            steps[0] = 1.0
        rows.append(np.cumprod(steps))
    exposure = np.array(draw(st.lists(unit, min_size=n_years, max_size=n_years)))
    rate = draw(st.floats(0.0, 0.2))
    probabilities = np.array(draw(st.lists(unit, min_size=n_draws, max_size=n_draws)))
    losses = np.array(
        draw(st.lists(st.floats(0.0, 2.0), min_size=n_draws, max_size=n_draws))
    )
    max_events = draw(st.sampled_from([None, 0, 1, 2, 3]))
    return np.array(rows), exposure, rate, probabilities, losses, max_events


@settings(max_examples=300, **PROPERTY_SETTINGS)
@given(case=event_cases())
def test_event_loss_matches_exhaustive_path_enumeration(case):
    survival, exposure, rate, probabilities, losses, max_events = case
    discount = (1.0 + rate) ** -np.arange(survival.shape[1])
    actual = expected_event_loss(
        survival, exposure, discount, probabilities, losses, max_events
    )
    expected = [
        enumerate_event_loss(row, exposure, discount, p, loss, max_events)
        for row, p, loss in zip(survival, probabilities, losses)
    ]
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-15)


@settings(max_examples=100, **PROPERTY_SETTINGS)
@given(case=event_cases(), rates=st.lists(st.floats(0.0, 0.2), min_size=2, max_size=2))
def test_event_loss_falls_with_the_discount_rate_and_rises_with_the_cap(case, rates):
    survival, exposure, _, probabilities, losses, _ = case
    low, high = sorted(rates)
    years = np.arange(survival.shape[1])
    by_rate = [
        expected_event_loss(
            survival, exposure, (1.0 + r) ** -years, probabilities, losses, 1
        )
        for r in (low, high)
    ]
    assert np.all(by_rate[1] <= by_rate[0] + 1e-15)
    discount = (1.0 + low) ** -years
    by_cap = [
        expected_event_loss(survival, exposure, discount, probabilities, losses, cap)
        for cap in (0, 1, 2, 3, None)
    ]
    for smaller, larger in zip(by_cap, by_cap[1:]):
        assert np.all(smaller <= larger + 1e-15)
    assert np.array_equal(by_cap[0], np.zeros_like(by_cap[0]))
    uncapped = expected_event_loss(
        survival, exposure, discount, probabilities, losses, None
    )
    assert np.array_equal(
        expected_event_loss(
            survival, exposure, discount, probabilities, losses, survival.shape[1]
        ),
        uncapped,
    )


def _certain_event_in_year(year: int, rate: float, loss: float) -> float:
    exposure = np.zeros(year + 1)
    exposure[year] = 1.0
    harm = HarmEffect(
        "event", event_probability=point(1.0), event_qaly_loss=point(loss)
    )
    return float(
        _simulate_harm_draws(
            [harm],
            np.ones((1, year + 1)),
            exposure,
            (1.0 + rate) ** -np.arange(year + 1, dtype=float),
            np.random.default_rng(0),
            1,
        )[0]
    )


@pytest.mark.parametrize(
    "year,rate,loss",
    [
        *itertools.product((0, 1, 2), (0.0, 0.03, 0.1), (0.1, 1.0)),
        (3, 0.1, 0.5),
        (10, 0.03, 0.02),
    ],
)
def test_audit_event_harm_is_discounted_to_its_year(year, rate, loss):
    """Audit: a certain year-two loss was -1.0 at 3%, not -1/1.03."""
    assert _certain_event_in_year(year, rate, loss) == pytest.approx(
        -loss / (1.0 + rate) ** year, rel=1e-14
    )


def test_audit_event_counterexample_values():
    assert _certain_event_in_year(1, 0.03, 1.0) == pytest.approx(
        -0.970873786407767, rel=1e-14
    )
    assert _certain_event_in_year(3, 0.1, 0.5) == pytest.approx(
        -0.37565740045078877, rel=1e-14
    )


@pytest.mark.parametrize(
    "survival,probability,expected",
    [
        # The audited engine drew events at rates .672435 and .639845.
        ([1.0, 0.5, 0.25], 0.5, 0.65625),
        ([1.0, 0.8, 0.6, 0.4, 0.2], 0.3, 0.611766),
    ],
)
def test_audit_first_event_risk_is_not_overcounted(survival, probability, expected):
    n = 5
    harm = HarmEffect(
        "event", event_probability=point(probability), event_qaly_loss=point(1.0)
    )
    losses = -_simulate_harm_draws(
        [harm],
        np.tile(survival, (n, 1)),
        np.ones(len(survival)),
        np.ones(len(survival)),
        np.random.default_rng(42),
        n,
    )
    np.testing.assert_allclose(losses, expected, rtol=1e-14)


@pytest.mark.parametrize(
    "age,probability,expected",
    [
        # Audited engine: .6712 and .78332 over 100,000 Bernoulli draws.
        (95, 0.3, 0.6381638811877043),
        (97, 0.5, 0.7668374360993012),
    ],
)
def test_audit_public_first_event_probability(age, probability, expected):
    harm = HarmEffect(
        "event", event_probability=point(probability), event_qaly_loss=point(1.0)
    )
    result = simulate_qaly_profile_vectorized(
        make_item(1.0, harms=(harm,)),
        make_profile(age),
        n_simulations=8,
        random_state=53,
        discount_rate=0,
    )
    _, _, survival = reference_path(make_profile(age), np.ones(MAX_AGE - age))
    oracle = sum(
        s * (1 - probability) ** t * probability for t, s in enumerate(survival)
    )
    assert oracle == pytest.approx(expected, rel=1e-12)
    assert -result.expected_harm_qalys == pytest.approx(oracle, rel=1e-12)


def test_shipped_hbot_event_harm_is_now_discount_sensitive():
    """Audit: identical -0.0023046875 at 0%, 3% and 10%."""
    harm = HarmEffect(
        "barotrauma_or_oxygen_toxicity",
        event_probability=point(0.003),
        event_qaly_loss=point(0.02),
    )
    item = make_item(None, harms=(harm,))
    profile = make_profile(40)
    _, _, survival = reference_path(profile, np.ones(MAX_AGE - 40))
    harms = []
    for rate in (0.0, 0.03, 0.1):
        result = simulate_qaly_profile_vectorized(
            item, profile, n_simulations=64, random_state=0, discount_rate=rate
        )
        oracle = sum(
            0.02 * 0.003 * s * 0.997**t / (1 + rate) ** t
            for t, s in enumerate(survival)
        )
        assert -result.expected_harm_qalys == pytest.approx(oracle, rel=1e-12)
        harms.append(result.expected_harm_qalys)
    assert harms[0] < harms[1] < harms[2] < 0


@settings(max_examples=40, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    probability=st.floats(0.0, 1.0),
    loss=st.floats(0.0, 1.0),
    annual=st.floats(0.0, 0.05),
    seed=st.integers(0, 2**16),
)
def test_each_draw_carries_the_expected_event_loss(
    profile, probability, loss, annual, seed
):
    """Point-valued harms have no parameter uncertainty, so every draw is equal."""
    harms = (
        HarmEffect(
            "event",
            event_probability=point(probability),
            event_qaly_loss=point(loss),
            annual_qaly_loss=point(annual),
        ),
    )
    result, gains = draws(make_item(1.0, harms=harms), profile, random_state=seed)
    assert np.all(gains == gains[0])
    assert result.std == 0.0
    assert result.ci95[0] <= result.mean <= result.ci95[1]


@settings(max_examples=40, **PROPERTY_SETTINGS)
@given(
    item=uncertain_items(),
    profile=profiles,
    seed=st.integers(0, 2**16),
    active_years=st.one_of(st.none(), st.floats(0.0, 30.0)),
)
def test_full_persistence_continuation_view_equals_the_primary_view(
    item, profile, seed, active_years
):
    rule = InteractionRule(
        "stack",
        requires_tags=["t"],
        annual_qaly_loss=Distribution("uniform", {"min": 0.0, "max": 0.01}),
        event_probability=Distribution("uniform", {"min": 0.0, "max": 0.2}),
        event_qaly_loss=point(0.3),
    )
    item.interaction_rules = [rule]
    result = simulate_qaly_profile_vectorized(
        item,
        profile,
        n_simulations=32,
        annual_persistence=1.0,
        active_years=active_years,
        active_interaction_tags=["t"],
        random_state=seed,
    )
    assert result.continuation_adjusted_mean == result.mean
    assert (
        result.continuation_adjusted_cost_factor
        == result.expected_discounted_cost_factor
    )
    assert result.continuation_adjusted_qol_factor == result.expected_qol_factor
    assert result.continuation_adjusted_life_years_gained == result.life_years_gained


def test_policy_views_share_harm_parameter_draws():
    """Common random numbers: each view scales the same annual-loss draws.

    With a null HR every view shares the baseline survival, so a view's harm is
    the same per-draw loss times that view's deterministic exposure. The audit
    measured .0034 QALYs of pure resampling noise between identical views.
    """
    harm = HarmEffect(
        "uncertain", annual_qaly_loss=Distribution("uniform", {"min": 0.0, "max": 0.02})
    )
    profile = make_profile(60)
    result = simulate_qaly_profile_vectorized(
        make_item(None, harms=(harm,)),
        profile,
        n_simulations=64,
        annual_persistence=0.7,
        random_state=11,
    )
    _, _, survival = reference_path(profile, np.ones(MAX_AGE - 60))
    discount = 1.03 ** -np.arange(MAX_AGE - 60)
    full = float(np.sum(np.array(survival) * discount))
    continuation = float(np.sum(np.array(survival) * discount * 0.7 ** np.arange(40)))
    assert result.continuation_adjusted_mean / result.mean == pytest.approx(
        continuation / full, rel=1e-12
    )
    assert result.one_year_mean / result.mean == pytest.approx(1.0 / full, rel=1e-12)


def test_invalid_event_cap_is_rejected():
    for cap in (-1, 1.5, True):
        with pytest.raises(ValueError, match="max_events"):
            expected_event_loss([1.0, 0.9], [1.0, 1.0], [1.0, 1.0], 0.1, 1.0, cap)


# ---------------------------------------------------------------------------
# Zero remaining horizon
# ---------------------------------------------------------------------------

EXPOSURE_FIELDS = (
    "expected_discounted_cost_factor",
    "continuation_adjusted_cost_factor",
    "one_year_cost_factor",
    "expected_qol_factor",
    "continuation_adjusted_qol_factor",
    "one_year_qol_factor",
)


@pytest.mark.parametrize("age", [100, 101, 120])
@pytest.mark.parametrize("active_years", [None, 0, 5])
def test_no_modeled_years_means_no_exposure(age, active_years):
    """Audit: ages 100 and 101 returned cost factor 1 with no modeled year."""
    harm = HarmEffect(
        "h",
        annual_qaly_loss=point(0.01),
        event_probability=point(0.1),
        event_qaly_loss=point(1.0),
    )
    item = make_item(0.7, harms=(harm,))
    profile = make_profile(age)
    results = [
        simulate_qaly_profile_vectorized(
            item, profile, n_simulations=4, active_years=active_years, random_state=0
        ),
        simulate_qaly_profile(item, profile, n_simulations=4, random_state=0),
        simulate_qaly(item, age, "female", n_simulations=4, random_state=0),
    ]
    for result in results:
        for field in EXPOSURE_FIELDS:
            assert getattr(result, field) == 0.0, field
        assert result.expected_qol_weights == ()
        assert result.mean == result.expected_harm_qalys == 0.0
        assert result.one_year_mean == result.continuation_adjusted_mean == 0.0


def test_zero_active_years_keeps_a_one_year_hypothetical_view():
    """With years remaining, active_years=0 stops the primary policy only."""
    result = simulate_qaly_profile_vectorized(
        make_item(0.7),
        make_profile(60),
        n_simulations=4,
        active_years=0,
        random_state=0,
    )
    assert result.expected_discounted_cost_factor == 0.0
    assert result.mean == 0.0
    assert result.one_year_cost_factor == 1.0
    assert result.one_year_mean > 0.0


# ---------------------------------------------------------------------------
# Survival and remaining-QALY bounds, the null effect and determinism
# ---------------------------------------------------------------------------


@settings(max_examples=80, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    hrs=st.lists(st.floats(1e-3, 50.0), min_size=1, max_size=4),
    baseline_hazard_multiplier=st.floats(0.0, 10.0),
    onset=st.floats(0.0, 10.0),
    ramp=st.floats(0.0, 5.0),
    decay=st.floats(0.0, 1.0),
    exposure_seed=st.integers(0, 2**16),
)
def test_policy_survival_is_a_non_increasing_probability(
    profile, hrs, baseline_hazard_multiplier, onset, ramp, decay, exposure_seed
):
    n_years = MAX_AGE - profile.age
    base_qx = np.minimum(
        np.array(
            [get_mortality_rate(profile.age + t, profile.sex) for t in range(n_years)]
        )
        * table_multiplier(profile)
        * baseline_hazard_multiplier,
        0.99,
    )
    exposure = np.random.default_rng(exposure_seed).uniform(0.0, 1.0, n_years)
    quality = np.full((len(hrs), n_years), 0.8)
    discount = np.ones(n_years)
    *_, survival, _ = _simulate_reversible_policy(
        base_qx,
        np.array(hrs),
        exposure,
        mortality_effect_fraction(n_years, onset, ramp, decay),
        quality,
        discount,
        discount,
        np.zeros(len(hrs)),
    )
    assert np.all(survival[:, 0] == 1.0)
    assert np.all((survival >= 0.0) & (survival <= 1.0))
    assert np.all(np.diff(survival, axis=1) <= 0.0)


@settings(max_examples=60, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    hr=st.floats(0.05, 50.0),
    log_sd=st.floats(0.0, 1.5),
    discount_rate=discount_rates,
    seed=st.integers(0, 2**16),
)
def test_remaining_qalys_never_go_negative(profile, hr, log_sd, discount_rate, seed):
    item = Intervention(
        "wide",
        "wide",
        "other",
        mortality=MortalityEffect(
            Distribution("lognormal", {"hr": hr, "log_sd": log_sd})
        ),
    )
    with quality_noise_disabled():
        _, gains = draws(
            item,
            profile,
            n_simulations=64,
            random_state=seed,
            discount_rate=discount_rate,
        )
    baseline, _, _ = reference_path(
        profile, np.ones(MAX_AGE - profile.age), discount_rate=discount_rate
    )
    assert np.all(baseline + gains >= -1e-12)


@pytest.mark.parametrize("hr", [2.0, 3.0, 10.0])
def test_audit_harmful_hr_cannot_leave_negative_remaining_life(hr):
    """Audit: age 98 high-risk male, HR 3 left -0.6825 remaining QALYs."""
    profile = make_profile(98, high_risk=True)
    with quality_noise_disabled():
        gain = simulate_qaly_profile(
            make_item(hr), profile, n_simulations=1, random_state=53
        ).mean
    baseline, _, _ = reference_path(profile, np.ones(2))
    policy, _, _ = reference_path(profile, np.full(2, hr))
    assert baseline == pytest.approx(0.7572815533980582, rel=1e-12)
    assert baseline + gain == pytest.approx(policy, rel=1e-12)
    assert baseline + gain >= 0.0


@settings(max_examples=60, **PROPERTY_SETTINGS)
@given(
    profile=profiles,
    onset=st.floats(0.0, 20.0),
    ramp=st.floats(0.0, 5.0),
    decay=st.floats(0.0, 1.0),
    persistence=st.floats(0.0, 1.0),
    active_years=st.one_of(st.none(), st.floats(0.0, 50.0)),
    discount_rate=discount_rates,
    baseline_hazard_multiplier=baseline_hazard_multipliers,
    lognormal=st.booleans(),
)
def test_null_hazard_ratio_has_exactly_zero_mortality_effect(
    profile,
    onset,
    ramp,
    decay,
    persistence,
    active_years,
    discount_rate,
    baseline_hazard_multiplier,
    lognormal,
):
    hazard_ratio = (
        Distribution("lognormal", {"hr": 1.0, "log_sd": 0.0})
        if lognormal
        else point(1.0)
    )
    item = Intervention(
        "null",
        "null",
        "other",
        mortality=MortalityEffect(
            hazard_ratio, onset_delay=onset, ramp_up=ramp, decay_rate=decay
        ),
        confounding_prior=ConfoundingPrior(alpha=2.0, beta=2.0),
    )
    result, gains = draws(
        item,
        profile,
        annual_persistence=persistence,
        active_years=active_years,
        discount_rate=discount_rate,
        baseline_hazard_multiplier=baseline_hazard_multiplier,
    )
    assert np.all(gains == 0.0)
    assert result.life_years_gained == 0.0
    assert result.continuation_adjusted_mean == 0.0
    assert result.continuation_adjusted_life_years_gained == 0.0
    assert result.one_year_mean == 0.0
    assert result.one_year_life_years_gained == 0.0


@settings(max_examples=25, **PROPERTY_SETTINGS)
@given(item=uncertain_items(), profile=profiles, seed=st.integers(0, 2**16))
def test_same_seed_gives_identical_results(item, profile, seed):
    kwargs = dict(
        n_simulations=32,
        random_state=seed,
        annual_persistence=0.8,
        active_interaction_tags=["t", "t"],
    )
    first, first_draws = draws(item, profile, **kwargs)
    second, second_draws = draws(item, profile, **kwargs)
    assert asdict(first) == asdict(second)
    assert np.array_equal(first_draws, second_draws)


HASH_SEED_SCRIPT = """
from dataclasses import asdict
from optiqal.combination import simulate_combined_qaly
from optiqal.intervention import Distribution, HarmEffect, InteractionRule, Intervention, MortalityEffect
from optiqal.profile import Profile
from optiqal.simulate import simulate_qaly_profile_vectorized

rules = [
    InteractionRule(rid, requires_tags=[tag], minimum_matches=2,
                    annual_qaly_loss=Distribution("uniform", {"min": 0.0, "max": 0.01}),
                    event_probability=Distribution("point", {"value": 0.05}),
                    event_qaly_loss=Distribution("point", {"value": 0.2}))
    for rid, tag in (("r1", "sedating"), ("r2", "bleeding"), ("r3", "sedating"))
]
items = [
    Intervention(f"i{k}", f"i{k}", "other",
                 mortality=MortalityEffect(Distribution("lognormal", {"hr": 0.9, "log_sd": 0.2})),
                 harm_model=[HarmEffect("h", annual_qaly_loss=Distribution("uniform", {"min": 0.0, "max": 0.004}))],
                 interaction_tags=["sedating", "bleeding"], interaction_rules=rules[k:])
    for k in range(3)
]
profile = Profile(45, "female", "overweight", "former", False)
print(asdict(simulate_qaly_profile_vectorized(
    items[0], profile, n_simulations=64, random_state=7,
    active_interaction_tags={"sedating", "bleeding", "sedating_2", "x", "y"})))
print(asdict(simulate_combined_qaly(items, profile, n_simulations=64, random_state=7)))
"""


def test_results_do_not_depend_on_the_hash_seed():
    python_dir = Path(__file__).resolve().parents[1]
    outputs = []
    for hash_seed in ("0", "1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": str(python_dir)}
        completed = subprocess.run(
            [sys.executable, "-c", HASH_SEED_SCRIPT],
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1] == outputs[2]
    assert outputs[0].count("{") >= 2


# ---------------------------------------------------------------------------
# Combined stacks: harms preserved, shared rules charged once
# ---------------------------------------------------------------------------


def _annual_harm(harm_id: str, loss: float) -> HarmEffect:
    return HarmEffect(harm_id, annual_qaly_loss=point(loss))


def _event_harm(harm_id: str, probability: float, loss: float) -> HarmEffect:
    return HarmEffect(
        harm_id, event_probability=point(probability), event_qaly_loss=point(loss)
    )


def test_combined_stack_carries_every_members_harms():
    """Before: the stack deep-copied the first item and dropped the rest's harms."""
    profile = make_profile(50)
    a = make_item(1.0, harms=(_annual_harm("sedation", 0.01),), item_id="a")
    b = make_item(1.0, harms=(_event_harm("bleed", 0.01, 0.2),), item_id="b")
    c = make_item(None, harms=(_annual_harm("gi", 0.002),), item_id="c")
    singles = [
        simulate_combined_qaly([item], profile, n_simulations=8, random_state=0)
        for item in (a, b, c)
    ]
    stack = simulate_combined_qaly([a, b, c], profile, n_simulations=8, random_state=0)
    assert stack.expected_harm_qalys == pytest.approx(
        sum(single.expected_harm_qalys for single in singles), rel=1e-12
    )
    assert stack.mean == pytest.approx(stack.expected_harm_qalys, rel=1e-12)
    reversed_stack = simulate_combined_qaly(
        [c, b, a], profile, n_simulations=8, random_state=0
    )
    assert reversed_stack.expected_harm_qalys == pytest.approx(
        stack.expected_harm_qalys, rel=1e-12
    )


def test_one_item_stack_matches_the_same_item_with_a_null_partner():
    profile = make_profile(45)
    item = make_item(
        0.85,
        harms=(_annual_harm("sedation", 0.004), _event_harm("fall", 0.02, 0.1)),
        item_id="a",
    )
    null_partner = make_item(None, item_id="null")
    alone = simulate_combined_qaly([item], profile, n_simulations=32, random_state=5)
    paired = simulate_combined_qaly(
        [item, null_partner], profile, n_simulations=32, random_state=5
    )
    assert paired.mean == pytest.approx(alone.mean, rel=1e-9)
    assert paired.expected_harm_qalys == pytest.approx(
        alone.expected_harm_qalys, rel=1e-9
    )


@pytest.mark.parametrize("allocation", ["per_item", "split_across_matches"])
def test_shared_interaction_rule_is_charged_once_for_the_stack(allocation):
    rule = InteractionRule(
        "sedation_stack",
        requires_tags=["sedating"],
        minimum_matches=2,
        allocation=allocation,
        annual_qaly_loss=point(0.01),
        event_probability=point(0.02),
        event_qaly_loss=point(0.1),
    )
    profile = make_profile(55)
    a = make_item(1.0, tags=("sedating",), rules=(rule,), item_id="a")
    b = make_item(1.0, tags=("sedating",), rules=(rule,), item_id="b")
    stack = simulate_combined_qaly([a, b], profile, n_simulations=8, random_state=0)

    # One whole-rule charge on the stack's (baseline) survival.
    _, _, survival = reference_path(profile, np.ones(MAX_AGE - 55))
    survival = np.array(survival)
    discount = 1.03 ** -np.arange(MAX_AGE - 55)
    no_event_before = np.concatenate([[1.0], np.cumprod(np.full(44, 0.98))])
    once = 0.01 * np.sum(survival * discount) + 0.1 * np.sum(
        discount * survival * 0.02 * no_event_before
    )
    assert stack.expected_interaction_harm_qalys == pytest.approx(-once, rel=1e-12)
    # The stack-level penalty function agrees for the same pair.
    catalog = {item.id: _catalog_entry_with_rule(item.id, rule) for item in (a, b)}
    penalty, _ = expected_stack_interaction_qaly(["a", "b"], catalog, profile)
    assert penalty == pytest.approx(-once, rel=1e-12)


def _catalog_entry_with_rule(item_id, rule):
    from optiqal.catalog import CatalogEntry

    return CatalogEntry(
        id=item_id,
        name=item_id,
        category="supplement_current",
        hr_observed=1.0,
        log_sd=0.05,
        conf_alpha=1.0,
        conf_beta=1.0,
        annual_cost=0,
        interaction_tags=["sedating"],
        interaction_rules=[rule],
    )


def test_combined_stack_applies_the_profile_modifier_once():
    """Seeded version of the double-application guard in test_combination."""
    profile = Profile(40, "male", "normal", "never", False, activity_level="sedentary")
    a = make_item(0.85, item_id="ex1")
    a.category = "exercise"
    b = make_item(0.90, item_id="ex2")
    b.category = "exercise"
    modified = math.exp(1.2 * (math.log(0.85) + math.log(0.90)))
    with quality_noise_disabled():
        stack = simulate_combined_qaly([a, b], profile, n_simulations=4, random_state=0)
    base, _, _ = reference_path(profile, np.ones(60))
    policy, _, _ = reference_path(profile, np.full(60, modified))
    assert stack.mean == pytest.approx(policy - base, rel=1e-9)
