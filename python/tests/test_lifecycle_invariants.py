"""Invariants of LifecycleModel, checked against an independent recurrence.

The reference recurrence below takes only the packaged data tables (life
table, quality weights, cause fractions) and re-derives the annual
survival x quality x discount sum from scratch, with its own interpolation, so
an error in ``optiqal.lifecycle``'s interpolators or HR mixing cannot cancel
out. It follows the model's documented semantics: start-of-year survival,
baseline mortality = life-table rate x multiplier capped at 0.99, intervention
mortality = that capped baseline x the cause-weighted HR, capped again at 0.99,
and a joint stop once both survival curves are below 0.001.

Regression cases reproduce the minimized counterexamples from the 2026-09-25
invariants audit; each asserts the correct value rather than the old one.
"""

import math
from dataclasses import dataclass

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

import optiqal.simulate as simulate
from optiqal.intervention import Distribution, Intervention, MortalityEffect
from optiqal.lifecycle import (
    CAUSE_FRACTIONS,
    CDC_LIFE_TABLE,
    QUALITY_WEIGHTS,
    LifecycleModel,
    PathwayHRs,
    get_cause_fraction,
)
from optiqal.profile import (
    Profile,
    get_baseline_mortality_multiplier,
    get_intervention_modifier,
)

PATHWAYS = ("cvd", "cancer", "other")
MORTALITY_CAP = 0.99
TRUNCATION = 0.001


# ---------------------------------------------------------------------------
# Independent reference recurrence
# ---------------------------------------------------------------------------


def _interpolate(table: dict, age: float, *, log: bool) -> float:
    """Piecewise interpolation between anchor ages, flat beyond both ends."""
    anchors = sorted(table)
    if age <= anchors[0]:
        return table[anchors[0]]
    if age >= anchors[-1]:
        return table[anchors[-1]]
    upper = next(anchor for anchor in anchors if anchor > age)
    lower = anchors[anchors.index(upper) - 1]
    weight = (age - lower) / (upper - lower)
    low, high = table[lower], table[upper]
    if log:
        # Geometric interpolation, i.e. linear in log mortality.
        return low * (high / low) ** weight
    return low + weight * (high - low)


def _cause_fraction(age: float, pathway: str) -> float:
    column = {anchor: row[pathway] for anchor, row in CAUSE_FRACTIONS.items()}
    return _interpolate(column, age, log=False)


@dataclass
class Reference:
    baseline_qalys: float
    intervention_qalys: float
    baseline_life_years: float
    intervention_life_years: float

    @property
    def qaly_gain(self) -> float:
        return self.intervention_qalys - self.baseline_qalys

    @property
    def life_years_gained(self) -> float:
        return self.intervention_life_years - self.baseline_life_years


def reference_lifecycle(
    start_age: int,
    sex: str,
    hrs,
    *,
    max_age: int = 100,
    discount_rate: float = 0.03,
    multiplier: float = 1.0,
) -> Reference:
    """From-scratch lifecycle recurrence.

    ``hrs`` is either one flat HR applied to all-cause mortality or a
    ``(cvd, cancer, other)`` tuple mixed by the cause fractions, which sum to 1
    (see ``test_cause_fractions_sum_to_one``).
    """
    baseline_survival = intervention_survival = 1.0
    reference = Reference(0.0, 0.0, 0.0, 0.0)
    for year in range(max(0, max_age - start_age)):
        age = start_age + year
        base_qx = min(
            _interpolate(CDC_LIFE_TABLE[sex], age, log=True) * multiplier,
            MORTALITY_CAP,
        )
        if isinstance(hrs, tuple):
            scale = sum(
                _cause_fraction(age, pathway) * hr for pathway, hr in zip(PATHWAYS, hrs)
            )
        else:
            scale = hrs
        intervention_qx = min(base_qx * scale, MORTALITY_CAP)
        weight = _interpolate(QUALITY_WEIGHTS, age, log=False) * (
            1 + discount_rate
        ) ** (-year)

        reference.baseline_qalys += baseline_survival * weight
        reference.intervention_qalys += intervention_survival * weight
        reference.baseline_life_years += baseline_survival
        reference.intervention_life_years += intervention_survival

        baseline_survival *= 1 - base_qx
        intervention_survival *= 1 - intervention_qx
        if baseline_survival < TRUNCATION and intervention_survival < TRUNCATION:
            break
    return reference


def _run(start_age, sex, hrs, **kwargs):
    if not isinstance(hrs, tuple):
        hrs = (hrs, hrs, hrs)
    return LifecycleModel(start_age, sex, **kwargs).calculate(PathwayHRs(*hrs))


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

sexes = st.sampled_from(["male", "female"])
start_ages = st.integers(min_value=0, max_value=110)
max_ages = st.integers(min_value=0, max_value=130)
# The defaults (3%, multiplier 1) are the most-used configuration and the one
# the retired precomputed-baseline cache keyed on, so draw them often.
discount_rates = st.just(0.03) | st.floats(min_value=0.0, max_value=0.10)
multipliers = st.just(1.0) | st.floats(min_value=0.0, max_value=10.0)
protective_hr = st.floats(min_value=0.0, max_value=1.0)
harmful_hr = st.floats(min_value=1.0, max_value=100.0)
any_hr = st.floats(min_value=0.0, max_value=100.0)
pathway_hrs = st.tuples(any_hr, any_hr, any_hr)


# ---------------------------------------------------------------------------
# Data preconditions the reference relies on
# ---------------------------------------------------------------------------


def test_cause_fractions_sum_to_one():
    """The flat-HR shortcut is exact only if the cause mix sums to 1."""
    for anchor, row in CAUSE_FRACTIONS.items():
        assert math.isclose(sum(row.values()), 1.0, abs_tol=1e-12), anchor
        assert all(value > 0 for value in row.values()), anchor
    for age in range(0, 131):
        fractions = get_cause_fraction(age)
        assert math.isclose(sum(fractions.values()), 1.0, abs_tol=1e-12), age
        reference = sum(_cause_fraction(age, pathway) for pathway in PATHWAYS)
        assert math.isclose(reference, 1.0, abs_tol=1e-12), age


def test_life_table_rates_are_probabilities():
    for sex, table in CDC_LIFE_TABLE.items():
        assert all(0 < rate < 1 for rate in table.values()), sex


# ---------------------------------------------------------------------------
# Regression cases from the audit's minimized counterexamples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("use_precomputed", [True, False])
def test_one_year_horizon_null_intervention_is_exactly_zero(use_precomputed):
    """Audit: max_age=41 at 40 returned -18.859 with the horizon-100 cache."""
    result = LifecycleModel(
        start_age=40, sex="male", max_age=41, use_precomputed=use_precomputed
    ).calculate(PathwayHRs(1, 1, 1))
    assert result.qaly_gain == 0.0
    assert result.life_years_gained == 0.0
    # One year alive at the age-40 quality weight, midway between the 35 and 45
    # anchors: (0.922 + 0.904) / 2.
    assert result.baseline_qalys == pytest.approx(0.913, abs=1e-12)
    assert result.intervention_qalys == result.baseline_qalys


@pytest.mark.parametrize("use_precomputed", [True, False])
def test_zero_horizon_null_intervention_is_exactly_zero(use_precomputed):
    """Verifier: max_age == start_age returned -21.038 with the cache."""
    result = LifecycleModel(
        start_age=40, sex="female", max_age=40, use_precomputed=use_precomputed
    ).calculate(PathwayHRs(1, 1, 1))
    assert result.qaly_gain == 0.0
    assert result.life_years_gained == 0.0
    assert result.baseline_qalys == 0.0
    assert result.intervention_qalys == 0.0


@pytest.mark.parametrize("use_precomputed", [True, False])
def test_extended_horizon_null_intervention_is_exactly_zero(use_precomputed):
    """Verifier: age 98 to max_age 120 returned +1.518 with the cache."""
    result = LifecycleModel(
        start_age=98, sex="female", max_age=120, use_precomputed=use_precomputed
    ).calculate(PathwayHRs(1, 1, 1))
    reference = reference_lifecycle(98, "female", 1.0, max_age=120)
    assert result.qaly_gain == 0.0
    assert result.life_years_gained == 0.0
    assert result.baseline_qalys == pytest.approx(reference.baseline_qalys, rel=1e-9)


@pytest.mark.parametrize(
    ("hr", "multiplier"),
    [
        (3.0, 8.0),  # Verifier: remaining QALYs -0.6844660194174756
        (10.0, 1.0),  # Verifier: remaining QALYs -0.2795825400311527
    ],
)
def test_harmful_hr_cannot_make_remaining_qalys_negative(hr, multiplier):
    result = _run(
        98, "male", hr, baseline_mortality_multiplier=multiplier, use_precomputed=False
    )
    # Intervention mortality saturates at the 0.99 cap in both modeled years
    # (ages 98 and 99, quality weight 0.75): 0.75 x (1 + 0.01 / 1.03).
    capped = 0.75 * (1 + 0.01 / 1.03)
    assert result.intervention_qalys == pytest.approx(capped, rel=1e-12)
    assert result.intervention_qalys >= 0
    assert result.baseline_qalys + result.qaly_gain == pytest.approx(
        result.intervention_qalys, abs=1e-12
    )
    if multiplier == 8.0:
        # The adjusted baseline is already at the cap, so a harmful HR cannot
        # raise mortality further.
        assert result.qaly_gain == 0.0
        assert result.life_years_gained == 0.0


@pytest.mark.parametrize("pathway", PATHWAYS)
@pytest.mark.parametrize("bad", [-0.5, -1e-12, math.nan, math.inf, -math.inf])
def test_rejects_negative_or_non_finite_pathway_hr(pathway, bad):
    hrs = {name: 1.0 for name in PATHWAYS}
    hrs[pathway] = bad
    with pytest.raises(ValueError, match=f"{pathway} hazard ratio"):
        LifecycleModel(40, "male").calculate(PathwayHRs(**hrs))


@pytest.mark.parametrize("bad", [-0.1, math.nan, math.inf])
def test_rejects_negative_or_non_finite_mortality_multiplier(bad):
    with pytest.raises(ValueError, match="baseline_mortality_multiplier"):
        LifecycleModel(40, "male", baseline_mortality_multiplier=bad)


@pytest.mark.parametrize("bad", [-0.01, 0.2, math.nan, math.inf])
def test_rejects_unsupported_discount_rate(bad):
    with pytest.raises(ValueError):
        LifecycleModel(40, "male", discount_rate=bad)


def test_zero_hr_is_accepted_and_bounded():
    """HR 0 removes the pathway entirely; survival then stays at 1."""
    result = _run(90, "male", 0.0, max_age=95)
    everyone_survives = sum(
        _interpolate(QUALITY_WEIGHTS, 90 + year, log=False) * 1.03**-year
        for year in range(5)
    )
    assert result.intervention_qalys == pytest.approx(everyone_survives, rel=1e-12)
    assert result.life_years_gained == pytest.approx(
        5 - reference_lifecycle(90, "male", 1.0, max_age=95).baseline_life_years,
        rel=1e-12,
    )
    assert result.qaly_gain > 0


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    max_age=max_ages,
    discount_rate=discount_rates,
    multiplier=multipliers,
    use_precomputed=st.booleans(),
)
@example(40, "male", 41, 0.03, 1.0, True)
@example(40, "female", 40, 0.03, 1.0, True)
@example(98, "female", 120, 0.03, 1.0, True)
@example(40, "male", 100, 0.03, 1.0, True)
def test_null_intervention_is_exactly_zero_everywhere(
    start_age, sex, max_age, discount_rate, multiplier, use_precomputed
):
    """All pathway HRs = 1 reproduce the baseline bit for bit."""
    result = LifecycleModel(
        start_age,
        sex,
        discount_rate=discount_rate,
        max_age=max_age,
        use_precomputed=use_precomputed,
        baseline_mortality_multiplier=multiplier,
    ).calculate(PathwayHRs(1.0, 1.0, 1.0))
    assert result.qaly_gain == 0.0
    assert result.life_years_gained == 0.0
    assert result.intervention_qalys == result.baseline_qalys
    assert result.pathway_contributions == {"cvd": 0.0, "cancer": 0.0, "other": 0.0}


@settings(max_examples=150, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    max_age=max_ages,
    discount_rate=discount_rates,
    multiplier=multipliers,
    hrs=st.just((1.0, 1.0, 1.0)) | pathway_hrs,
)
@example(40, "male", 41, 0.03, 1.0, (1.0, 1.0, 1.0))
@example(40, "male", 100, 0.03, 1.0, (0.75, 0.87, 0.90))
def test_use_precomputed_cannot_change_any_result(
    start_age, sex, max_age, discount_rate, multiplier, hrs
):
    kwargs = dict(
        discount_rate=discount_rate,
        max_age=max_age,
        baseline_mortality_multiplier=multiplier,
    )
    cached = _run(start_age, sex, hrs, use_precomputed=True, **kwargs)
    fresh = _run(start_age, sex, hrs, use_precomputed=False, **kwargs)
    assert cached == fresh


@settings(max_examples=300, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    max_age=max_ages,
    discount_rate=discount_rates,
    multiplier=multipliers,
    hrs=pathway_hrs,
)
@example(98, "male", 100, 0.03, 8.0, (3.0, 3.0, 3.0))
@example(98, "male", 100, 0.03, 1.0, (10.0, 10.0, 10.0))
@example(0, "female", 130, 0.0, 10.0, (100.0, 100.0, 100.0))
def test_remaining_qalys_are_nonnegative_and_bounded(
    start_age, sex, max_age, discount_rate, multiplier, hrs
):
    """Survival in [0, 1] means remaining QALYs lie in [0, horizon years]."""
    result = _run(
        start_age,
        sex,
        hrs,
        max_age=max_age,
        discount_rate=discount_rate,
        baseline_mortality_multiplier=multiplier,
    )
    horizon = max(0, max_age - start_age)
    assert 0 <= result.baseline_qalys <= horizon
    assert 0 <= result.intervention_qalys <= horizon
    assert result.baseline_qalys + result.qaly_gain == pytest.approx(
        result.intervention_qalys, abs=1e-9
    )
    reference = reference_lifecycle(
        start_age,
        sex,
        hrs,
        max_age=max_age,
        discount_rate=discount_rate,
        multiplier=multiplier,
    )
    # Remaining life years with the intervention, from the reference baseline
    # plus the model's own gain.
    assert reference.baseline_life_years + result.life_years_gained >= -1e-9


@settings(max_examples=200, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    max_age=max_ages,
    discount_rate=discount_rates,
    multiplier=multipliers,
    hr=any_hr,
)
@example(40, "male", 100, 0.03, 1.0, 0.8)
@example(98, "male", 100, 0.03, 8.0, 3.0)
@example(20, "female", 130, 0.0, 2.0, 0.05)
def test_flat_hr_matches_independent_recurrence(
    start_age, sex, max_age, discount_rate, multiplier, hr
):
    """Equal pathway HRs h act as one all-cause HR on the capped baseline.

    The reference applies qx' = min(min(qx * m, 0.99) * h, 0.99) without cause
    fractions, so the model's cause mixing must collapse to h exactly as the
    fractions summing to 1 imply.
    """
    result = _run(
        start_age,
        sex,
        hr,
        max_age=max_age,
        discount_rate=discount_rate,
        baseline_mortality_multiplier=multiplier,
    )
    reference = reference_lifecycle(
        start_age,
        sex,
        hr,
        max_age=max_age,
        discount_rate=discount_rate,
        multiplier=multiplier,
    )
    assert result.baseline_qalys == pytest.approx(
        reference.baseline_qalys, rel=1e-9, abs=1e-12
    )
    assert result.intervention_qalys == pytest.approx(
        reference.intervention_qalys, rel=1e-9, abs=1e-12
    )
    assert result.qaly_gain == pytest.approx(reference.qaly_gain, rel=1e-9, abs=1e-9)
    assert result.life_years_gained == pytest.approx(
        reference.life_years_gained, rel=1e-9, abs=1e-9
    )


@settings(max_examples=200, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    max_age=max_ages,
    discount_rate=discount_rates,
    multiplier=multipliers,
    hrs=pathway_hrs,
)
def test_pathway_hrs_match_independent_recurrence(
    start_age, sex, max_age, discount_rate, multiplier, hrs
):
    result = _run(
        start_age,
        sex,
        hrs,
        max_age=max_age,
        discount_rate=discount_rate,
        baseline_mortality_multiplier=multiplier,
    )
    reference = reference_lifecycle(
        start_age,
        sex,
        hrs,
        max_age=max_age,
        discount_rate=discount_rate,
        multiplier=multiplier,
    )
    assert result.intervention_qalys == pytest.approx(
        reference.intervention_qalys, rel=1e-9, abs=1e-12
    )
    assert result.qaly_gain == pytest.approx(reference.qaly_gain, rel=1e-9, abs=1e-9)
    assert result.life_years_gained == pytest.approx(
        reference.life_years_gained, rel=1e-9, abs=1e-9
    )


@settings(max_examples=200, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    max_age=max_ages,
    discount_rate=discount_rates,
    multiplier=multipliers,
    weaker=st.tuples(protective_hr, protective_hr, protective_hr),
    shrink=st.tuples(protective_hr, protective_hr, protective_hr),
)
def test_protective_hr_gains_and_lower_hr_gains_more(
    start_age, sex, max_age, discount_rate, multiplier, weaker, shrink
):
    stronger = tuple(hr * factor for hr, factor in zip(weaker, shrink))
    kwargs = dict(
        max_age=max_age,
        discount_rate=discount_rate,
        baseline_mortality_multiplier=multiplier,
    )
    weak = _run(start_age, sex, weaker, **kwargs)
    strong = _run(start_age, sex, stronger, **kwargs)
    assert weak.qaly_gain >= 0.0
    assert weak.life_years_gained >= 0.0
    assert strong.qaly_gain >= weak.qaly_gain - 1e-12
    assert strong.life_years_gained >= weak.life_years_gained - 1e-12
    # Every modeled year gains, so the per-pathway split accounts for the total.
    contributions = weak.pathway_contributions
    assert all(value >= 0 for value in contributions.values())
    assert sum(contributions.values()) == pytest.approx(weak.qaly_gain, abs=1e-9)


@settings(max_examples=150, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    max_age=max_ages,
    discount_rate=discount_rates,
    multiplier=multipliers,
    hrs=st.tuples(harmful_hr, harmful_hr, harmful_hr),
)
def test_harmful_hr_never_gains(
    start_age, sex, max_age, discount_rate, multiplier, hrs
):
    result = _run(
        start_age,
        sex,
        hrs,
        max_age=max_age,
        discount_rate=discount_rate,
        baseline_mortality_multiplier=multiplier,
    )
    assert result.qaly_gain <= 0.0
    assert result.life_years_gained <= 0.0


@settings(max_examples=150, deadline=None)
@given(
    start_age=start_ages,
    sex=sexes,
    horizons=st.tuples(max_ages, max_ages).map(sorted),
    discount_rate=discount_rates,
    multiplier=multipliers,
    hrs=st.tuples(protective_hr, protective_hr, protective_hr),
)
@example(98, "female", [100, 120], 0.03, 1.0, (0.5, 0.5, 0.5))
def test_protective_gain_does_not_shrink_with_longer_horizon(
    start_age, sex, horizons, discount_rate, multiplier, hrs
):
    shorter, longer = (
        _run(
            start_age,
            sex,
            hrs,
            max_age=max_age,
            discount_rate=discount_rate,
            baseline_mortality_multiplier=multiplier,
        )
        for max_age in horizons
    )
    assert longer.qaly_gain >= shorter.qaly_gain - 1e-12
    assert longer.life_years_gained >= shorter.life_years_gained - 1e-12


# ---------------------------------------------------------------------------
# Differential: LifecycleModel vs the vectorized engine
# ---------------------------------------------------------------------------


def _reference_profile(age: int, sex: str) -> Profile:
    return Profile(age, sex, "normal", "never", False, activity_level="moderate")


def test_reference_profile_never_triggers_lifecycle_truncation():
    """Precondition for the tight tolerance below.

    A normal-BMI never-smoker at moderate activity has multiplier 1, and baseline
    survival from any start age to 100 stays above 0.001 (it bottoms out near
    0.023), so LifecycleModel's early stop, which needs both curves below
    0.001, never fires before 100. Both engines then sum the same years.
    """
    for sex in ("male", "female"):
        assert get_baseline_mortality_multiplier(_reference_profile(40, sex)) == 1.0
        assert get_intervention_modifier(_reference_profile(40, sex), "other") == 1.0
        survival = 1.0
        for age in range(0, 100):
            survival *= 1 - _interpolate(CDC_LIFE_TABLE[sex], age, log=True)
        assert survival > 10 * TRUNCATION


@settings(max_examples=60, deadline=None)
@given(
    age=st.integers(min_value=18, max_value=99),
    sex=sexes,
    hr=st.floats(min_value=0.05, max_value=3.0),
)
@example(40, "male", 0.8)
@example(20, "female", 1.2)
@example(90, "male", 0.05)
def test_lifecycle_matches_vector_engine_flat_hr(age, sex, hr):
    """LifecycleModel with equal pathway HRs matches the vector engine's point HR.

    Quality heterogeneity is switched off (QUALITY_WEIGHT_STD = 0) so each
    engine integrates the mean quality weights, confounding is off, the item's
    category carries no profile modifier, and both integrate to age 100.
    LifecycleModel stops once both survival curves fall below 0.001, while the
    vector engine always runs to 100; had that stop fired, each dropped year
    would move each series by under 0.001 x quality x discount. For this
    profile it cannot fire (see the precondition test above), so the two sum
    the same years and differ only by floating-point rounding, hence 1e-9.
    """
    profile = _reference_profile(age, sex)
    item = Intervention(
        "flat_hr",
        "Flat HR",
        "other",
        mortality=MortalityEffect(Distribution("point", {"value": hr})),
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(simulate, "QUALITY_WEIGHT_STD", 0.0)
        vector = simulate.simulate_qaly_profile_vectorized(
            item,
            profile,
            n_simulations=1,
            discount_rate=0.03,
            apply_confounding=False,
            random_state=0,
        )
    lifecycle = LifecycleModel(
        age,
        sex,
        discount_rate=0.03,
        max_age=100,
        baseline_mortality_multiplier=get_baseline_mortality_multiplier(profile),
    ).calculate(PathwayHRs(hr, hr, hr))
    assert lifecycle.qaly_gain == pytest.approx(vector.mean, rel=1e-9, abs=1e-9)
    assert lifecycle.life_years_gained == pytest.approx(
        vector.life_years_gained, rel=1e-9, abs=1e-9
    )
