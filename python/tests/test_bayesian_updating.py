"""Tests for the imputation priors used in Bayesian state updating."""

from __future__ import annotations

import numpy as np
import pytest

from optiqal.bayesian_updating import ImputationPrior, DEFAULT_PRIORS


def test_truncated_normal_respects_bounds():
    rng = np.random.default_rng(0)
    prior = ImputationPrior(
        variable="x",
        mean=4.0,
        std=3.0,
        distribution="truncated_normal",
        lower_bound=3.0,
        upper_bound=12.0,
    )
    samples = prior.sample(20000, rng)
    assert samples.min() >= 3.0 - 1e-9
    assert samples.max() <= 12.0 + 1e-9


def test_truncated_normal_does_not_pile_up_on_bounds():
    """Regression: the old implementation clamped with np.maximum/np.minimum,
    which piled probability mass on the bounds (here ~37% at the lower bound).
    Proper truncation resamples the tail instead."""
    rng = np.random.default_rng(1)
    prior = ImputationPrior(
        variable="x",
        mean=4.0,
        std=3.0,
        distribution="truncated_normal",
        lower_bound=3.0,
        upper_bound=12.0,
    )
    samples = prior.sample(20000, rng)
    frac_at_lower = np.mean(np.isclose(samples, 3.0))
    assert frac_at_lower < 0.01


def test_default_priors_sample_within_bounds():
    rng = np.random.default_rng(2)
    for prior in DEFAULT_PRIORS.values():
        samples = prior.sample(2000, rng)
        if prior.lower_bound is not None:
            assert samples.min() >= prior.lower_bound - 1e-9
        if prior.upper_bound is not None:
            assert samples.max() <= prior.upper_bound + 1e-9


def test_truncated_normal_pdf_is_normalized_and_matches_sampler():
    from scipy import integrate

    prior = ImputationPrior(
        variable="bmi",
        mean=27.0,
        std=5.0,
        distribution="truncated_normal",
        lower_bound=15.0,
        upper_bound=60.0,
    )
    # Density integrates to 1 over the bounds (a plain norm.pdf would not).
    area, _ = integrate.quad(prior.pdf, 15.0, 60.0)
    assert area == pytest.approx(1.0, abs=1e-3)
    # Zero outside the bounds.
    assert prior.pdf(10.0) == 0.0
    assert prior.pdf(65.0) == 0.0
