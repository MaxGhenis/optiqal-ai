"""Tests for confounding module."""

import numpy as np
import pytest

from optiqal.confounding import (
    CATEGORY_PRIORS,
    ConfoundingPrior,
    adjust_hr,
    calculate_e_value,
    get_confounding_prior,
)


class TestConfoundingPrior:
    def test_mean_calculation(self):
        prior = ConfoundingPrior(alpha=2, beta=2)
        assert prior.mean == 0.5

    def test_sample_in_range(self):
        prior = ConfoundingPrior(alpha=2, beta=5)
        samples = prior.sample(1000, random_state=42)
        assert all(0 <= s <= 1 for s in samples)

    def test_ci_contains_mean(self):
        prior = ConfoundingPrior(alpha=3, beta=3)
        ci = prior.ci(0.95)
        assert ci[0] < prior.mean < ci[1]


class TestCategoryPriors:
    def test_all_categories_defined(self):
        expected = [
            "exercise",
            "diet",
            "sleep",
            "stress",
            "substance",
            "medical",
            "social",
            "other",
        ]
        for cat in expected:
            assert cat in CATEGORY_PRIORS

    def test_exercise_skeptical(self):
        """Exercise should have skeptical prior (mean < 0.5)."""
        prior = CATEGORY_PRIORS["exercise"]
        assert prior.mean < 0.5

    def test_medical_less_skeptical(self):
        """Medical interventions (RCTs) should be less skeptical."""
        exercise = CATEGORY_PRIORS["exercise"]
        medical = CATEGORY_PRIORS["medical"]
        assert medical.mean > exercise.mean


class TestGetConfoundingPrior:
    def test_rct_adjustment(self):
        """RCT evidence should increase causal fraction."""
        cohort = get_confounding_prior("exercise", "cohort")
        rct = get_confounding_prior("exercise", "rct")
        assert rct.mean > cohort.mean

    def test_mendelian_randomization(self):
        """MR should be treated like RCT."""
        mr = get_confounding_prior("diet", "mendelian-randomization")
        rct = get_confounding_prior("diet", "rct")
        assert abs(mr.mean - rct.mean) < 0.1


class TestAdjustHR:
    def test_full_causation(self):
        """With causal_fraction=1, HR unchanged."""
        assert adjust_hr(0.8, 1.0) == 0.8

    def test_no_causation(self):
        """With causal_fraction=0, HR becomes 1."""
        assert adjust_hr(0.8, 0.0) == 1.0

    def test_partial_causation(self):
        """Partial causation moves HR toward 1."""
        adjusted = adjust_hr(0.8, 0.5)
        assert 0.8 < adjusted < 1.0

    def test_harmful_intervention(self):
        """HR > 1 should also work."""
        adjusted = adjust_hr(1.5, 0.5)
        assert 1.0 < adjusted < 1.5


class TestEValue:
    def test_protective_effect(self):
        """E-value for protective effect (HR < 1)."""
        e_val, interpretation = calculate_e_value(0.7)
        assert e_val > 1
        assert isinstance(interpretation, str)

    def test_null_effect(self):
        """E-value for null effect (HR = 1) should be 1."""
        e_val, interpretation = calculate_e_value(1.0)
        assert e_val == 1.0
        assert "susceptible" in interpretation.lower()

    def test_harmful_effect(self):
        """E-value for harmful effect (HR > 1)."""
        e_val, interpretation = calculate_e_value(1.5)
        assert e_val > 1

    def test_stronger_effect_higher_evalue(self):
        """Stronger effects need more confounding to explain away."""
        weak, _ = calculate_e_value(0.9)
        strong, _ = calculate_e_value(0.7)
        assert strong > weak


class TestHrLognormalMeanCentering:
    """Verify HR → lognormal parameters produce the expected mean."""

    def test_mean_equals_hr(self):
        from optiqal.confounding import hr_to_lognormal_params

        params = hr_to_lognormal_params(0.80, log_sd=0.15)
        # E[Lognormal(mu, sigma)] = exp(mu + sigma**2 / 2) should equal hr.
        mean = np.exp(params["log_mean"] + params["log_sd"] ** 2 / 2)
        assert abs(mean - 0.80) < 1e-9

    def test_null_hr_samples_mean_to_one(self):
        from optiqal.confounding import hr_to_lognormal_params
        from optiqal.intervention import Distribution

        params = hr_to_lognormal_params(1.0, log_sd=0.12)
        dist = Distribution(type="lognormal", params=params)
        samples = dist.sample(200_000, random_state=7)
        # With mean-centering a null HR samples to E[HR] = 1.0 exactly, not
        # exp(sigma**2 / 2) ≈ 1.007.
        assert abs(float(np.mean(samples)) - 1.0) < 0.002

    def test_rejects_nonpositive_hr(self):
        from optiqal.confounding import hr_to_lognormal_params

        with pytest.raises(ValueError):
            hr_to_lognormal_params(0, log_sd=0.1)
        with pytest.raises(ValueError):
            hr_to_lognormal_params(1.0, log_sd=-0.01)


class TestTieredPublicationBias:
    """Tiered pub-bias shrinkage by study quality."""

    def test_preregistered_rct_loses_less(self):
        """Preregistered RCTs with hard endpoints keep most of their effect."""
        from optiqal.confounding import (
            publication_bias_correct,
            shrinkage_for_study_quality,
        )

        hr_tier = publication_bias_correct(
            0.80, study_quality="rct_preregistered_hard_endpoint"
        )
        hr_industry = publication_bias_correct(
            0.80, study_quality="supplement_industry_rct"
        )
        # The industry tier should leave a weaker (closer-to-1) effect.
        assert hr_industry > hr_tier
        # Sanity: preregistered RCT is only 10% shrinkage.
        assert shrinkage_for_study_quality("rct_preregistered_hard_endpoint") == 0.10
        assert shrinkage_for_study_quality("supplement_industry_rct") == 0.50

    def test_tier_overrides_fallback(self):
        """When study_quality is provided it wins over the fallback shrinkage."""
        from optiqal.confounding import publication_bias_correct

        # Caller demands 90% shrinkage, but tier says 10% — tier wins.
        hr_tier = publication_bias_correct(
            0.80,
            shrinkage=0.90,
            study_quality="rct_preregistered_hard_endpoint",
        )
        # With only 10% shrinkage of log(0.80), HR is ~0.82.
        assert 0.81 < hr_tier < 0.84

    def test_unknown_tier_falls_back(self):
        """Unknown tier strings use the fallback shrinkage."""
        from optiqal.confounding import publication_bias_correct

        hr = publication_bias_correct(
            0.80, shrinkage=0.30, study_quality="nonexistent_tier"
        )
        hr_noqual = publication_bias_correct(0.80, shrinkage=0.30)
        assert abs(hr - hr_noqual) < 1e-9

    def test_animal_tier_very_weak(self):
        """Animal-only tier should shrink effect toward null aggressively."""
        from optiqal.confounding import publication_bias_correct

        hr = publication_bias_correct(0.70, study_quality="animal_or_mechanistic")
        # 70% shrinkage of log(0.70) = -0.107, exp ≈ 0.898
        assert 0.88 < hr < 0.92
