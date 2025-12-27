"""
Tests for mortality multiplier calculations.

Architecture: Risk factors are split between two modules to avoid double-counting:
- profile.py: BMI, smoking, activity level (lifestyle factors)
- markov.py HealthState: diabetes, hypertension (medical conditions)

The precompute script passes:
1. get_baseline_mortality_multiplier(profile) as intervention_hr
2. HealthState(diabetes=..., hypertension=...) as initial_state
"""

import pytest
import numpy as np
from optiqal.profile import Profile, get_baseline_mortality_multiplier
from optiqal.markov import HealthState, simulate_lifetime_markov


def simulate_life_expectancy(profile: Profile, n_sims: int = 200, seed: int = 42) -> float:
    """Helper to get median death age for a profile."""
    rng = np.random.default_rng(seed)

    mortality_multiplier = get_baseline_mortality_multiplier(profile)
    initial_state = HealthState(
        diabetes=profile.has_diabetes,
        hypertension=profile.has_hypertension,
    )

    life_years = []
    for _ in range(n_sims):
        result = simulate_lifetime_markov(
            start_age=profile.age,
            sex=profile.sex,
            intervention_hr=mortality_multiplier,
            initial_state=initial_state,
            rng=rng,
        )
        life_years.append(result.life_years)

    return profile.age + np.median(life_years)


class TestMortalityMultiplierArchitecture:
    """Verify risk factors are handled in the correct module."""

    def test_profile_multiplier_excludes_conditions(self):
        """Profile multiplier should NOT include diabetes/hypertension."""
        profile_healthy = Profile(
            age=50, sex="male", bmi_category="normal", smoking_status="never",
            has_diabetes=False, has_hypertension=False, activity_level="light",
        )
        profile_diabetes = Profile(
            age=50, sex="male", bmi_category="normal", smoking_status="never",
            has_diabetes=True, has_hypertension=False, activity_level="light",
        )

        mult_healthy = get_baseline_mortality_multiplier(profile_healthy)
        mult_diabetes = get_baseline_mortality_multiplier(profile_diabetes)

        # Should be equal since diabetes is handled by HealthState, not here
        assert mult_healthy == mult_diabetes, (
            "Diabetes should not affect profile multiplier (handled by HealthState)"
        )

    def test_healthstate_includes_conditions(self):
        """HealthState should apply diabetes/hypertension multipliers."""
        state_healthy = HealthState()
        state_diabetes = HealthState(diabetes=True)
        state_both = HealthState(diabetes=True, hypertension=True)

        assert state_healthy.get_mortality_multiplier() == 1.0
        assert state_diabetes.get_mortality_multiplier() > 1.0  # Should be ~1.4 (attenuated)
        assert state_both.get_mortality_multiplier() > state_diabetes.get_mortality_multiplier()


class TestLifeExpectancyReasonableness:
    """Sanity checks on simulated life expectancy."""

    def test_healthy_35yo_male_life_expectancy(self):
        """
        A healthy 35yo male should live to ~75+.
        CDC 2021: 35yo male has ~43 years remaining (to age ~78).
        """
        profile = Profile(
            age=35,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="moderate",  # Meets guidelines
        )

        death_age = simulate_life_expectancy(profile, n_sims=300)

        # Be somewhat lenient since model includes condition acquisition
        assert death_age >= 73, (
            f"Healthy 35yo male dying at {death_age:.0f} is too early. "
            f"Expected ~78."
        )

    def test_diabetes_reduces_life_expectancy(self):
        """Diabetes should reduce life expectancy by ~5-10 years."""
        base_profile = Profile(
            age=50, sex="male", bmi_category="normal", smoking_status="never",
            has_diabetes=False, has_hypertension=False, activity_level="light",
        )
        diabetes_profile = Profile(
            age=50, sex="male", bmi_category="normal", smoking_status="never",
            has_diabetes=True, has_hypertension=False, activity_level="light",
        )

        death_age_healthy = simulate_life_expectancy(base_profile)
        death_age_diabetes = simulate_life_expectancy(diabetes_profile)

        life_years_lost = death_age_healthy - death_age_diabetes

        # Diabetes should reduce life expectancy by 1-10 years
        # (attenuated effect since CDC rates include average conditions)
        assert life_years_lost > 1, (
            f"Diabetes only reduced life by {life_years_lost:.1f} years (expected 1-10)"
        )
        assert life_years_lost < 10, (
            f"Diabetes reduced life by {life_years_lost:.1f} years (too aggressive, expected 1-10)"
        )

    def test_combined_risk_factors_effect(self):
        """Multiple risk factors should compound but not be extreme."""
        healthy = Profile(
            age=35, sex="male", bmi_category="normal", smoking_status="never",
            has_diabetes=False, has_hypertension=False, activity_level="moderate",
        )
        unhealthy = Profile(
            age=35, sex="male", bmi_category="obese", smoking_status="current",
            has_diabetes=True, has_hypertension=True, activity_level="light",
        )

        death_healthy = simulate_life_expectancy(healthy)
        death_unhealthy = simulate_life_expectancy(unhealthy)

        years_lost = death_healthy - death_unhealthy

        # Combined risk factors should reduce life by 10-30 years
        # (not 35+ years which would be unrealistic)
        assert years_lost >= 10, f"Only {years_lost:.0f} years lost with severe risk factors"
        assert years_lost <= 30, f"{years_lost:.0f} years lost is too extreme"

        # Unhealthy person should still live past 50 at median
        assert death_unhealthy >= 50, (
            f"35yo with risk factors dying at {death_unhealthy:.0f} is too early"
        )

    def test_life_expectancy_ordering(self):
        """Healthier profiles should outlive unhealthier ones."""
        profiles = [
            ("unhealthy", Profile(35, "male", "obese", "current", True, True, "sedentary")),
            ("average", Profile(35, "male", "overweight", "never", False, False, "light")),
            ("healthy", Profile(35, "male", "normal", "never", False, False, "moderate")),
        ]

        death_ages = {}
        for name, profile in profiles:
            death_ages[name] = simulate_life_expectancy(profile)

        assert death_ages["healthy"] > death_ages["average"], (
            f"Healthy ({death_ages['healthy']:.0f}) should outlive "
            f"average ({death_ages['average']:.0f})"
        )
        assert death_ages["average"] > death_ages["unhealthy"], (
            f"Average ({death_ages['average']:.0f}) should outlive "
            f"unhealthy ({death_ages['unhealthy']:.0f})"
        )


class TestProfileMultiplierValues:
    """Verify profile multiplier components are reasonable."""

    def test_bmi_effect(self):
        """Obesity should increase mortality multiplier."""
        normal = Profile(50, "male", "normal", "never", False, False, "light")
        obese = Profile(50, "male", "obese", "never", False, False, "light")
        severe = Profile(50, "male", "severely_obese", "never", False, False, "light")

        mult_normal = get_baseline_mortality_multiplier(normal)
        mult_obese = get_baseline_mortality_multiplier(obese)
        mult_severe = get_baseline_mortality_multiplier(severe)

        assert mult_obese > mult_normal
        assert mult_severe > mult_obese
        # Severe obesity ~2x, normal ~1.15 (from activity)
        assert mult_severe / mult_normal > 1.5

    def test_smoking_effect(self):
        """Current smoking should significantly increase mortality."""
        never = Profile(50, "male", "normal", "never", False, False, "light")
        current = Profile(50, "male", "normal", "current", False, False, "light")

        mult_never = get_baseline_mortality_multiplier(never)
        mult_current = get_baseline_mortality_multiplier(current)

        ratio = mult_current / mult_never
        # Current smoking RR ~2.8
        assert 2.5 <= ratio <= 3.2, f"Smoking effect ratio {ratio:.2f} outside expected range"

    def test_activity_effect(self):
        """Active lifestyle should reduce mortality."""
        sedentary = Profile(50, "male", "normal", "never", False, False, "sedentary")
        active = Profile(50, "male", "normal", "never", False, False, "active")

        mult_sedentary = get_baseline_mortality_multiplier(sedentary)
        mult_active = get_baseline_mortality_multiplier(active)

        # Sedentary ~1.4, active ~0.9 → ratio ~1.55
        assert mult_sedentary > mult_active
        assert mult_sedentary / mult_active > 1.4
