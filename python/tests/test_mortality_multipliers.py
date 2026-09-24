"""
Tests for the profile-level baseline mortality multiplier.

`profile.get_baseline_mortality_multiplier` combines the BMI, smoking and
activity relative risks. It deliberately leaves out diabetes and hypertension:
`web_api.build_baseline_response` applies `DIABETES_MORTALITY_RR` and
`HYPERTENSION_MORTALITY_RR` itself, on top of its own lifestyle product, so the
condition risks must not also appear in the profile multiplier.

These four tests survived rebuild PR B, which deleted the Markov simulator the
rest of the original file exercised. They cover only surviving code.
"""

from optiqal.profile import Profile, get_baseline_mortality_multiplier


class TestMortalityMultiplierArchitecture:
    """Verify the profile multiplier's scope."""

    def test_profile_multiplier_excludes_conditions(self):
        """Profile multiplier should NOT include diabetes/hypertension."""
        profile_healthy = Profile(
            age=50,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        )
        profile_diabetes = Profile(
            age=50,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=True,
            has_hypertension=False,
            activity_level="light",
        )

        mult_healthy = get_baseline_mortality_multiplier(profile_healthy)
        mult_diabetes = get_baseline_mortality_multiplier(profile_diabetes)

        assert mult_healthy == mult_diabetes, (
            "Diabetes should not affect the profile multiplier "
            "(web_api.build_baseline_response applies the condition RRs)"
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
        assert 2.5 <= ratio <= 3.2, (
            f"Smoking effect ratio {ratio:.2f} outside expected range"
        )

    def test_activity_effect(self):
        """Active lifestyle should reduce mortality."""
        sedentary = Profile(50, "male", "normal", "never", False, False, "sedentary")
        active = Profile(50, "male", "normal", "never", False, False, "active")

        mult_sedentary = get_baseline_mortality_multiplier(sedentary)
        mult_active = get_baseline_mortality_multiplier(active)

        # Sedentary ~1.4, active ~0.9 → ratio ~1.55
        assert mult_sedentary > mult_active
        assert mult_sedentary / mult_active > 1.4
