"""Tests for simulation module."""

import pytest
import numpy as np

from optiqal.intervention import Distribution, Intervention, MortalityEffect
from optiqal.confounding import ConfoundingPrior
from optiqal.simulate import simulate_qaly, SimulationResult


@pytest.fixture
def protective_intervention():
    """Intervention with protective mortality effect."""
    return Intervention(
        id="walking",
        name="Walking",
        category="exercise",
        mortality=MortalityEffect(
            hazard_ratio=Distribution(
                type="lognormal",
                params={"log_mean": -0.18, "log_sd": 0.08}
            )
        ),
        confounding_prior=ConfoundingPrior(alpha=2.5, beta=5.0),
    )


@pytest.fixture
def null_intervention():
    """Intervention with no mortality effect."""
    return Intervention(
        id="null",
        name="Null",
        category="other",
        mortality=None,
    )


class TestSimulateQALY:
    def test_returns_simulation_result(self, protective_intervention):
        result = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            random_state=42,
        )
        assert isinstance(result, SimulationResult)

    def test_positive_qaly_gain(self, protective_intervention):
        result = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            random_state=42,
        )
        assert result.median > 0
        assert result.mean > 0

    def test_confidence_interval_contains_median(self, protective_intervention):
        result = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            random_state=42,
        )
        assert result.ci95[0] < result.median < result.ci95[1]

    def test_null_intervention_zero_gain(self, null_intervention):
        result = simulate_qaly(
            null_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
        )
        assert result.median == 0
        assert result.mean == 0

    def test_pathway_contributions_sum(self, protective_intervention):
        result = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            random_state=42,
        )
        total = result.cvd_contribution + result.cancer_contribution + result.other_contribution
        # Allow some tolerance
        assert abs(total - result.median) < 0.5

    def test_confounding_reduces_effect(self, protective_intervention):
        with_confounding = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            apply_confounding=True,
            random_state=42,
        )
        without_confounding = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            apply_confounding=False,
            random_state=42,
        )
        # Confounding adjustment should reduce effect size
        assert with_confounding.median < without_confounding.median

    def test_younger_gains_more(self, protective_intervention):
        young = simulate_qaly(
            protective_intervention,
            age=30,
            sex="male",
            n_simulations=1000,
            random_state=42,
        )
        old = simulate_qaly(
            protective_intervention,
            age=70,
            sex="male",
            n_simulations=1000,
            random_state=42,
        )
        # Younger person has more years to benefit
        assert young.life_years_gained > old.life_years_gained

    def test_prob_positive(self, protective_intervention):
        result = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            random_state=42,
        )
        assert 0 <= result.prob_positive <= 1
        # Should be high for protective intervention
        assert result.prob_positive > 0.9

    def test_discounting_effect(self, protective_intervention):
        discounted = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            discount_rate=0.03,
            random_state=42,
        )
        undiscounted = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            discount_rate=0,
            random_state=42,
        )
        # Discounting should reduce QALY gain
        assert discounted.median < undiscounted.median
