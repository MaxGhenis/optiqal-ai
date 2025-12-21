"""Tests for confounding module."""

import pytest
import numpy as np

from optiqal.confounding import (
    ConfoundingPrior,
    CATEGORY_PRIORS,
    get_confounding_prior,
    adjust_hr,
    calculate_e_value,
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
        expected = ["exercise", "diet", "sleep", "stress", "substance", "medical", "social", "other"]
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
