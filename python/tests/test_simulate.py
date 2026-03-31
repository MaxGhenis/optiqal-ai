"""Tests for simulation module."""

import pytest
import numpy as np

from optiqal.intervention import (
    Distribution,
    HarmEffect,
    InteractionRule,
    Intervention,
    MortalityEffect,
)
from optiqal.confounding import ConfoundingPrior
from optiqal.profile import Profile
from optiqal.simulate import (
    effective_qol_factor_for_years,
    simulate_qaly,
    simulate_qaly_profile_vectorized,
    SimulationResult,
)


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


@pytest.fixture
def default_profile():
    """Representative healthy profile for profile-aware simulations."""
    return Profile(
        age=40,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="moderate",
    )


class TestSimulateQALY:
    def test_effective_qol_factor_for_years_truncates_weights(self):
        factor = effective_qol_factor_for_years((1.0, 0.9, 0.8), 2.5)

        assert factor == pytest.approx(2.3)

    def test_effective_qol_factor_for_years_uses_reasonable_fallback(self):
        factor = effective_qol_factor_for_years((), 10, fallback_factor=45.0)

        assert factor == pytest.approx(10.0)

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

    def test_zero_qaly_discount_is_idempotent(self, protective_intervention):
        first = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            discount_rate=0,
            random_state=42,
        )
        second = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=1000,
            discount_rate=0.0,
            random_state=42,
        )
        assert first.median == pytest.approx(second.median)

    def test_posterior_decision_metrics_are_coherent(self, protective_intervention):
        result = simulate_qaly(
            protective_intervention,
            age=40,
            sex="male",
            n_simulations=2000,
            random_state=42,
        )

        assert 0 <= result.prob_negative <= 1
        assert result.prob_positive + result.prob_negative == pytest.approx(1.0, abs=0.05)
        assert result.expected_upside >= 0
        assert result.expected_downside <= 0
        assert result.conditional_upside >= result.expected_upside
        assert result.conditional_downside <= result.expected_downside
        assert result.mean == pytest.approx(
            result.expected_upside + result.expected_downside,
            abs=1e-6,
        )

    def test_vectorized_default_discount_matches_canonical_rate(
        self, protective_intervention, default_profile
    ):
        default_result = simulate_qaly_profile_vectorized(
            protective_intervention,
            default_profile,
            n_simulations=2000,
            random_state=42,
        )
        explicit_result = simulate_qaly_profile_vectorized(
            protective_intervention,
            default_profile,
            n_simulations=2000,
            discount_rate=0.0,
            random_state=42,
        )

        assert default_result.discount_rate == pytest.approx(0.0)
        assert default_result.median == pytest.approx(explicit_result.median)
        assert default_result.mean == pytest.approx(explicit_result.mean)

    def test_vectorized_can_return_qaly_draws(
        self, protective_intervention, default_profile
    ):
        result, qaly_gains = simulate_qaly_profile_vectorized(
            protective_intervention,
            default_profile,
            n_simulations=2000,
            random_state=42,
            return_qaly_gains=True,
        )

        assert isinstance(result, SimulationResult)
        assert isinstance(qaly_gains, np.ndarray)
        assert qaly_gains.shape == (2000,)
        assert np.mean(qaly_gains) == pytest.approx(result.mean, abs=1e-9)
        assert np.mean(qaly_gains > 0) == pytest.approx(result.prob_positive, abs=1e-9)
        assert np.mean(qaly_gains < 0) == pytest.approx(result.prob_negative, abs=1e-9)

    def test_nonzero_qaly_discount_is_rejected(self, protective_intervention, default_profile):
        with pytest.raises(ValueError, match="0% QALY discounting only"):
            simulate_qaly_profile_vectorized(
                protective_intervention,
                default_profile,
                n_simulations=1000,
                discount_rate=0.03,
                random_state=42,
            )

    def test_direct_harm_model_can_make_net_effect_negative(self, default_profile):
        intervention = Intervention(
            id="harm_only",
            name="Harm Only",
            category="medical",
            mortality=MortalityEffect(
                hazard_ratio=Distribution(type="point", params={"value": 1.0}),
            ),
            harm_model=[
                HarmEffect(
                id="sedation",
                annual_qaly_loss=Distribution(type="point", params={"value": 0.01}),
            )
            ],
        )

        result = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=1000,
            random_state=42,
        )

        assert result.mean < 0
        assert result.expected_harm_qalys < 0
        assert result.prob_negative > 0.95

    def test_interaction_rule_uses_active_stack_tags(self, default_profile):
        intervention = Intervention(
            id="sedating_aid",
            name="Sedating aid",
            category="medical",
            mortality=MortalityEffect(
                hazard_ratio=Distribution(type="point", params={"value": 1.0}),
            ),
            interaction_tags=["sedating"],
            interaction_rules=[
                InteractionRule(
                    id="sedation_stack",
                    requires_tags=["sedating"],
                    minimum_matches=2,
                    annual_qaly_loss=Distribution(type="point", params={"value": 0.01}),
                )
            ],
        )

        alone = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=1000,
            random_state=42,
        )
        stacked = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=1000,
            active_interaction_tags=["sedating"],
            random_state=42,
        )

        assert alone.expected_interaction_harm_qalys == pytest.approx(0.0)
        assert stacked.expected_interaction_harm_qalys < 0
        assert stacked.mean < alone.mean

    def test_sleep_baseline_hazard_multiplier_changes_absolute_effect_size(
        self, protective_intervention, default_profile
    ):
        base = simulate_qaly_profile_vectorized(
            protective_intervention,
            default_profile,
            n_simulations=2000,
            random_state=42,
        )
        elevated = simulate_qaly_profile_vectorized(
            protective_intervention,
            default_profile,
            n_simulations=2000,
            baseline_hazard_multiplier=1.08,
            random_state=42,
        )

        assert elevated.mean > base.mean

    def test_global_intervention_hr_multiplier_can_create_effect_without_catalog_hr(
        self, default_profile
    ):
        intervention = Intervention(
            id="sleep_only",
            name="Sleep Only",
            category="medical",
            mortality=MortalityEffect(
                hazard_ratio=Distribution(type="point", params={"value": 1.0}),
            ),
        )

        base = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=2000,
            random_state=42,
        )
        improved = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=2000,
            global_intervention_hr_multiplier=0.98,
            random_state=42,
        )

        assert base.mean == pytest.approx(0.0, abs=1e-6)
        assert improved.mean > 0
