"""Invariants of the web API's baseline response.

The baseline checks compare ``build_baseline_response`` with an independent
oracle: a from-scratch life-table recurrence written here, which takes only
data (the CDC life table, the quality-weight table, the risk tables and the
calibration table) as input. They run over an exhaustive age grid for every
sex value and over Hypothesis-generated profiles.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st

from optiqal.lifecycle import CDC_LIFE_TABLE, CONDITION_DECREMENTS, QUALITY_WEIGHTS
from optiqal.profile import (
    ACTIVITY_MORTALITY_RR,
    BMI_MORTALITY_RR,
    DIABETES_MORTALITY_RR,
    HYPERTENSION_MORTALITY_RR,
    SMOKING_MORTALITY_RR,
)
from optiqal.sleep import (
    SleepMetrics,
    estimate_sleep_burden,
    sleep_baseline_mortality_multiplier,
)
from optiqal.web_api import (
    AGE_GROUP_BOUNDS,
    CALIBRATION_BY_AGE_SEX,
    CALIBRATION_BY_SEX,
    build_baseline_response,
)

# The projection contract the oracle implements. Survival is tracked to the
# start of each year up to HORIZON_END_AGE, the projection stops once under
# PROJECTION_FLOOR of the cohort is alive, and the published curve keeps the
# first year, every fifth age and every year with survival under
# CURVE_TAIL_SURVIVAL. "other" is a cohort that is half male and half female
# at the current age.
HORIZON_END_AGE = 110
PROJECTION_FLOOR = 0.001
CURVE_TAIL_SURVIVAL = 0.02
QALY_DISCOUNT_RATE = 0.03
MAX_ANNUAL_DEATH_PROBABILITY = 0.99
COHORT_SEXES = {"male": ("male",), "female": ("female",), "other": ("male", "female")}

HEALTHY = {
    "weight_kg": 75,
    "height_cm": 175,
    "smoker": False,
    "has_diabetes": False,
    "has_hypertension": False,
    "activity_level": "light",
}
HIGH_RISK = {
    "weight_kg": 150,
    "height_cm": 175,
    "smoker": True,
    "has_diabetes": True,
    "has_hypertension": True,
    "activity_level": "sedentary",
    "sleep_hours_per_night": 3,
}


# ---------------------------------------------------------------------------
# Independent oracle
# ---------------------------------------------------------------------------


def _interpolate(table: dict, age: float, *, log_scale: bool) -> float:
    """Piecewise interpolation of an age table, clamped at both ends."""
    ages = sorted(table)
    if age <= ages[0]:
        return float(table[ages[0]])
    if age >= ages[-1]:
        return float(table[ages[-1]])
    upper = next(a for a in ages if a > age)
    lower = max(a for a in ages if a <= age)
    fraction = (age - lower) / (upper - lower)
    low_value, high_value = float(table[lower]), float(table[upper])
    if log_scale and low_value > 0 and high_value > 0:
        return math.exp(
            math.log(low_value)
            + fraction * (math.log(high_value) - math.log(low_value))
        )
    return low_value + fraction * (high_value - low_value)


def _calibration(age: int, sex: str) -> float:
    for low, high, label in AGE_GROUP_BOUNDS:
        if low <= age <= high:
            return CALIBRATION_BY_AGE_SEX[label][sex]
    return CALIBRATION_BY_SEX[sex]


def _raw_multiplier(profile: dict) -> float:
    bmi = profile["weight_kg"] / (profile["height_cm"] / 100.0) ** 2
    if bmi < 25:
        category = "normal"
    elif bmi < 30:
        category = "overweight"
    elif bmi < 35:
        category = "obese"
    else:
        category = "severely_obese"
    multiplier = (
        BMI_MORTALITY_RR[category]
        * SMOKING_MORTALITY_RR["current" if profile.get("smoker") else "never"]
        * ACTIVITY_MORTALITY_RR[profile.get("activity_level", "light")]
    )
    if profile.get("has_diabetes"):
        multiplier *= DIABETES_MORTALITY_RR
    if profile.get("has_hypertension"):
        multiplier *= HYPERTENSION_MORTALITY_RR
    hours = profile.get("sleep_hours_per_night")
    if hours is not None:
        multiplier *= sleep_baseline_mortality_multiplier(
            estimate_sleep_burden(SleepMetrics(duration_hours=float(hours)))
        )
    return multiplier


@dataclass
class Oracle:
    survival: list[float]  # mixed-cohort survival to the start of each kept year
    quality: list[float]
    discount: list[float]
    life_expectancy: float
    qalys: float
    curve: list[tuple[int, float, float, float]]


def oracle_projection(profile: dict) -> Oracle:
    """Project the profile's cohort from the data tables alone."""
    age = int(profile["age"])
    raw = _raw_multiplier(profile)
    years = range(max(0, HORIZON_END_AGE - age + 1))
    per_sex = []
    for sex in COHORT_SEXES[profile.get("sex", "male")]:
        multiplier = raw / _calibration(age, sex)
        alive, series = 1.0, []
        for year in years:
            series.append(alive)
            death = min(
                _interpolate(CDC_LIFE_TABLE[sex], age + year, log_scale=True)
                * multiplier,
                MAX_ANNUAL_DEATH_PROBABILITY,
            )
            alive *= 1.0 - death
        per_sex.append(series)
    mixed = [sum(values) / len(values) for values in zip(*per_sex)]
    survival = []
    for alive in mixed:
        if alive < PROJECTION_FLOOR:
            break
        survival.append(alive)
    decrement = (
        CONDITION_DECREMENTS["diabetes"] if profile.get("has_diabetes") else 0
    ) + (CONDITION_DECREMENTS["hypertension"] if profile.get("has_hypertension") else 0)
    quality = [
        max(0.0, _interpolate(QUALITY_WEIGHTS, age + year, log_scale=False) - decrement)
        for year in range(len(survival))
    ]
    discount = [(1.0 + QALY_DISCOUNT_RATE) ** -year for year in range(len(survival))]
    curve = [
        (age + year, s, q, s * q * d)
        for year, (s, q, d) in enumerate(zip(survival, quality, discount))
        if year == 0 or (age + year) % 5 == 0 or s < CURVE_TAIL_SURVIVAL
    ]
    return Oracle(
        survival=survival,
        quality=quality,
        discount=discount,
        life_expectancy=sum(survival),
        qalys=sum(s * q * d for s, q, d in zip(survival, quality, discount)),
        curve=curve,
    )


def oracle_death_interval(oracle: Oracle) -> tuple[list[float], list[float]]:
    """p10/p90 years to death, and realized QALYs there, for the mixed cohort.

    The first year whose starting survival is at or below 1 - p is the p
    percentile; percentiles the projection never reaches take its last year.
    The QALYs are those accrued through that year.
    """
    years, qalys = [], []
    for threshold in (0.9, 0.1):
        year = next(
            (y for y, s in enumerate(oracle.survival) if s <= threshold),
            max(len(oracle.survival) - 1, 0),
        )
        years.append(float(year))
        qalys.append(
            sum(q * d for q, d in zip(oracle.quality[: year + 1], oracle.discount))
        )
    return years, qalys


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

# Values are published rounded; a published value may differ from the exact
# oracle value by half the last published digit plus float noise.
ROUNDING_4DP = 0.5e-4 + 1e-9
ROUNDING_1DP = 0.05 + 1e-9


def assert_baseline_invariants(profile: dict, response: dict) -> None:
    age = int(profile["age"])
    curve = response["survival_curve"]
    ages = [point["age"] for point in curve]
    assert ages == sorted(set(ages)), f"curve ages not increasing: {ages}"
    if curve:
        assert curve[0]["age"] == age and curve[0]["survival_probability"] == 1.0
    for point in curve:
        assert 0.0 <= point["survival_probability"] <= 1.0, point
        assert 0.0 <= point["quality_weight"] <= 1.0, point
        assert point["expected_qaly"] >= 0.0, point
    for earlier, later in zip(curve, curve[1:]):
        assert later["survival_probability"] <= earlier["survival_probability"], (
            f"survival rises from {earlier} to {later} for {profile}"
        )

    estimate = response["point_estimate"]
    assert estimate["remaining_life_expectancy"] >= 0.0
    assert estimate["remaining_qalys"] >= 0.0
    assert 0.0 <= estimate["current_quality_weight"] <= 1.0
    assert estimate["expected_death_age"] >= age
    for field in (
        "remaining_life_expectancy_ci",
        "expected_death_age_ci",
        "remaining_qalys_ci",
    ):
        low, high = estimate[field]
        assert 0.0 <= low <= high, f"{field} unordered or negative: {[low, high]}"


def assert_matches_oracle(profile: dict, response: dict) -> None:
    oracle = oracle_projection(profile)
    curve = response["survival_curve"]
    assert [point["age"] for point in curve] == [row[0] for row in oracle.curve]
    for point, (_, survival, quality, expected_qaly) in zip(curve, oracle.curve):
        assert abs(point["survival_probability"] - survival) <= ROUNDING_4DP, point
        assert abs(point["quality_weight"] - quality) <= ROUNDING_4DP, point
        assert abs(point["expected_qaly"] - expected_qaly) <= ROUNDING_4DP, point

    estimate = response["point_estimate"]
    age = int(profile["age"])
    assert abs(estimate["remaining_life_expectancy"] - oracle.life_expectancy) <= (
        ROUNDING_1DP
    )
    assert abs(estimate["expected_death_age"] - (age + oracle.life_expectancy)) <= (
        ROUNDING_1DP
    )
    assert abs(estimate["remaining_qalys"] - oracle.qalys) <= ROUNDING_1DP

    years, qalys = oracle_death_interval(oracle)
    for got, want in zip(estimate["remaining_life_expectancy_ci"], years):
        assert abs(got - want) <= ROUNDING_1DP
    for got, want in zip(estimate["expected_death_age_ci"], years):
        assert abs(got - (age + want)) <= ROUNDING_1DP
    for got, want in zip(estimate["remaining_qalys_ci"], qalys):
        assert abs(got - want) <= ROUNDING_1DP


# ---------------------------------------------------------------------------
# Mixed-sex ("other") survival
# ---------------------------------------------------------------------------


def test_other_sex_survival_minimized_audit_input_is_the_mixed_cohort():
    """Audit 2026-09-25 minimized input: survival read 0.0176 at 109 and
    0.0223 at 110, because age 109 carried only the male curve's point while
    age 110 averaged both sexes."""
    profile = {**HEALTHY, "age": 18, "sex": "other"}
    response = build_baseline_response({"profile": profile})
    by_age = {p["age"]: p["survival_probability"] for p in response["survival_curve"]}

    oracle = oracle_projection(profile)
    mixed_109, mixed_110 = oracle.survival[109 - 18], oracle.survival[110 - 18]
    assert mixed_109 > mixed_110 > CURVE_TAIL_SURVIVAL
    # 109 is neither a fifth age nor under the tail threshold for the mixture,
    # so it is not published; 110 is the mixed cohort's survival.
    assert 109 not in by_age
    assert by_age[110] == round(mixed_110, 4) == 0.0223
    assert_baseline_invariants(profile, response)
    assert_matches_oracle(profile, response)


def test_other_sex_high_risk_survival_matches_mixed_cohort():
    """Audit verifier input: survival read 0.0164 at 69 and 0.0533 at 70."""
    profile = {**HIGH_RISK, "age": 18, "sex": "other"}
    response = build_baseline_response({"profile": profile})
    by_age = {p["age"]: p["survival_probability"] for p in response["survival_curve"]}

    oracle = oracle_projection(profile)
    assert oracle.survival[69 - 18] > CURVE_TAIL_SURVIVAL
    assert 69 not in by_age
    assert by_age[70] == round(oracle.survival[70 - 18], 4)
    assert_baseline_invariants(profile, response)
    assert_matches_oracle(profile, response)


@pytest.mark.parametrize("sex", ["male", "female", "other"])
@pytest.mark.parametrize("risk", [HEALTHY, HIGH_RISK], ids=["healthy", "high_risk"])
def test_baseline_invariants_hold_for_every_age(sex, risk):
    """Exhaustive over ages 0..120, the whole range the API accepts."""
    for age in range(0, 121):
        profile = {**risk, "age": age, "sex": sex}
        response = build_baseline_response({"profile": profile})
        assert_baseline_invariants(profile, response)
        assert_matches_oracle(profile, response)


@pytest.mark.parametrize("risk", [HEALTHY, HIGH_RISK], ids=["healthy", "high_risk"])
def test_other_sex_estimates_lie_between_the_sexes(risk):
    """An equal mixture's expectations lie between those of its two halves.

    The tolerance covers one-decimal rounding of all three published values
    and the mixture keeping tail years that one sex alone would have dropped
    at the 0.1% projection floor.
    """
    for age in range(0, 121):
        estimates = {
            sex: build_baseline_response({"profile": {**risk, "age": age, "sex": sex}})[
                "point_estimate"
            ]
            for sex in ("male", "female", "other")
        }
        for field in ("remaining_life_expectancy", "remaining_qalys"):
            low = min(estimates["male"][field], estimates["female"][field])
            high = max(estimates["male"][field], estimates["female"][field])
            assert low - 0.15 <= estimates["other"][field] <= high + 0.15, (
                age,
                field,
                estimates,
            )


activity_levels = st.sampled_from(sorted(ACTIVITY_MORTALITY_RR))
baseline_profiles = st.fixed_dictionaries(
    {
        "age": st.integers(min_value=0, max_value=120),
        "sex": st.sampled_from(["male", "female", "other"]),
        "weight_kg": st.floats(min_value=20, max_value=500),
        "height_cm": st.floats(min_value=50, max_value=275),
        "smoker": st.booleans(),
        "has_diabetes": st.booleans(),
        "has_hypertension": st.booleans(),
        "activity_level": activity_levels,
    },
    optional={"sleep_hours_per_night": st.floats(min_value=0, max_value=24)},
)


@settings(max_examples=300, deadline=None)
@given(profile=baseline_profiles)
@example(profile={**HEALTHY, "age": 18, "sex": "other"})
@example(profile={**HIGH_RISK, "age": 0, "sex": "other"})
def test_baseline_invariants_hold_for_generated_profiles(profile):
    response = build_baseline_response({"profile": profile})
    assert_baseline_invariants(profile, response)
    assert_matches_oracle(profile, response)


# ---------------------------------------------------------------------------
# Male and female responses are unchanged by the mixed-cohort fix
# ---------------------------------------------------------------------------

# SHA-256 of ``json.dumps(response)`` (what scripts/web_baseline.py writes) from
# commit 3028e59f, before the "other" cohort was mixed on a common age grid.
# Only "other" may move; male and female output must stay byte-identical.
PINNED_BASELINE_DIGESTS = {
    "male_35_healthy_7h": (
        {"profile": {**HEALTHY, "age": 35, "sex": "male", "sleep_hours_per_night": 7}},
        "71632a1d841f0b5033349ab9234866b19604966362105a9ab81195297c4959f4",
    ),
    "female_35_healthy_7h": (
        {
            "profile": {
                **HEALTHY,
                "age": 35,
                "sex": "female",
                "sleep_hours_per_night": 7,
            }
        },
        "4810abe7d473a6cc07de201b51e9ffec11aeebb2a0837308d00a3e75c420c165",
    ),
    "male_18_healthy": (
        {"profile": {**HEALTHY, "age": 18, "sex": "male"}},
        "abe993cc7973dadb0b19cb7b652c4701f410b1b3ed80ea4ea6831934d7567086",
    ),
    "female_75_high_risk": (
        {"profile": {**HIGH_RISK, "age": 75, "sex": "female"}},
        "08c6551ede3e1bd29c96f4498104c53c914f7ea7be1f60d5490f420f65d5b381",
    ),
    "male_0_high_risk": (
        {"profile": {**HIGH_RISK, "age": 0, "sex": "male"}},
        "c5c851b1ae8bfd4b1ca06ce66d09a8a9739f818d97561ce1b055ccf6063ba36d",
    ),
    "female_100_healthy": (
        {"profile": {**HEALTHY, "age": 100, "sex": "female"}},
        "bf8643b946556aa1b16f38e323674291f900c912d6869215835a5ea82eca208f",
    ),
    "male_110_healthy": (
        {"profile": {**HEALTHY, "age": 110, "sex": "male"}},
        "e8ebbf06c6c03778b49f8ce6e0609280d67588299721481a7946a6fcb62284ee",
    ),
    "male_50_sleep_metrics": (
        {
            "profile": {
                **HEALTHY,
                "age": 50,
                "sex": "male",
                "sleep_hours_per_night": 7,
            },
            "sleep_metrics": {
                "duration_hours": 6.2,
                "spo2": 93,
                "snore_pct": 12,
                "routine_score": 60,
            },
        },
        "b586967a53182ddf87dab23df72b7b7e846cda38ef48db10288757896f0dc0a1",
    ),
}


@pytest.mark.parametrize("name", sorted(PINNED_BASELINE_DIGESTS))
def test_male_and_female_baseline_output_is_byte_identical(name):
    request, digest = PINNED_BASELINE_DIGESTS[name]
    text = json.dumps(build_baseline_response(request))
    assert hashlib.sha256(text.encode()).hexdigest() == digest, text
