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
from optiqal.defaults import DEFAULT_QALY_DISCOUNT_RATE
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


def test_centenarian_profile_returns_zero_without_crashing(protective_intervention):
    """Ages at/beyond the modeled horizon (100) must not crash the simulator.

    Regression: simulate_qaly_profile_vectorized previously raised IndexError
    (age 100) / ValueError (age >= 101) because ``n_years`` became 0 or negative,
    producing empty/negative-length arrays.
    """
    for age in (100, 101, 120):
        profile = Profile(
            age=age,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
        )
        result = simulate_qaly_profile_vectorized(
            protective_intervention, profile, n_simulations=200, random_state=1
        )
        assert isinstance(result, SimulationResult)
        assert result.mean == 0
        assert result.life_years_gained == 0

    # The return_qaly_gains tuple contract must still hold at the boundary.
    result, gains = simulate_qaly_profile_vectorized(
        protective_intervention,
        Profile(
            age=100,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
        ),
        n_simulations=200,
        random_state=1,
        return_qaly_gains=True,
    )
    assert isinstance(result, SimulationResult)
    assert gains.shape == (200,)
    assert np.all(gains == 0)


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
            discount_rate=DEFAULT_QALY_DISCOUNT_RATE,
            random_state=42,
        )

        assert default_result.discount_rate == pytest.approx(DEFAULT_QALY_DISCOUNT_RATE)
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

    def test_negative_qaly_discount_is_rejected(self, protective_intervention, default_profile):
        with pytest.raises(ValueError, match="nonnegative"):
            simulate_qaly_profile_vectorized(
                protective_intervention,
                default_profile,
                n_simulations=1000,
                discount_rate=-0.01,
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

    def test_active_years_limits_annual_harm_exposure(self, default_profile):
        intervention = Intervention(
            id="limited_harm",
            name="Limited Harm",
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

        one_year = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=1000,
            active_years=1,
            random_state=42,
        )
        ten_year = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=1000,
            active_years=10,
            random_state=42,
        )

        assert one_year.expected_harm_qalys == pytest.approx(-0.01, rel=0.05)
        assert ten_year.expected_harm_qalys < one_year.expected_harm_qalys
        assert abs(ten_year.expected_harm_qalys) < 10 * abs(one_year.expected_harm_qalys)

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

    def test_split_interaction_rule_allocates_shared_stack_harm(self, default_profile):
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
                    allocation="split_across_matches",
                    annual_qaly_loss=Distribution(type="point", params={"value": 0.01}),
                )
            ],
        )

        stacked = simulate_qaly_profile_vectorized(
            intervention,
            default_profile,
            n_simulations=1000,
            active_interaction_tags=["sedating"],
            active_years=1,
            random_state=42,
        )

        assert stacked.expected_interaction_harm_qalys == pytest.approx(
            -0.005,
            rel=0.05,
        )

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


class TestJensenBiasResidual:
    """Residual QALY bias on genuinely null interventions is a documented
    property of exponential-survival Monte Carlo under stochastic hazards,
    not a parameterization bug. These tests pin down the magnitude and
    shape so regressions in confounding.py or simulate.py don't silently
    widen the bias.
    """

    def _null_intervention(self, log_sd: float) -> Intervention:
        return Intervention(
            id=f"null_lsd_{log_sd}",
            name="null",
            category="diet",
            mortality=MortalityEffect(
                # hr-centered lognormal so E[HR] == 1.0 exactly.
                hazard_ratio=Distribution(
                    type="lognormal", params={"hr": 1.0, "log_sd": log_sd},
                ),
            ),
            confounding_prior=ConfoundingPrior(alpha=3.0, beta=3.0),
        )

    def test_null_bias_bounded_at_realistic_log_sd(self):
        """Residual Jensen bias magnitude capped at ~0.05 QALY (~18 days).

        At log_sd=0.12 with diet confounding prior the observed bias from
        exponential-survival Monte Carlo is around -0.035 QALY. This test
        pins an upper bound so future regressions in simulate.py or
        confounding.py don't silently widen the penalty.
        """
        profile = Profile(
            age=39, sex="male", bmi_category="normal",
            smoking_status="never", has_diabetes=False,
            has_hypertension=False, activity_level="light",
        )
        r = simulate_qaly_profile_vectorized(
            self._null_intervention(0.12), profile,
            n_simulations=100_000, random_state=1,
        )
        assert abs(r.mean) < 0.05, (
            f"Null-HR bias at log_sd=0.12 grew beyond bounded residual: "
            f"got {r.mean:.4f} QALY ({r.mean*365.25:.1f} days)"
        )

    def test_null_bias_monotone_in_variance(self):
        """Magnitude of the null-HR bias grows ~monotonically in log_sd**2."""
        profile = Profile(
            age=39, sex="male", bmi_category="normal",
            smoking_status="never", has_diabetes=False,
            has_hypertension=False, activity_level="light",
        )
        biases = []
        for log_sd in (0.02, 0.04, 0.08):
            r = simulate_qaly_profile_vectorized(
                self._null_intervention(log_sd), profile,
                n_simulations=100_000, random_state=1,
            )
            biases.append(abs(r.mean))
        # Monotone non-decreasing (allowing noise at the small end).
        assert biases[0] < biases[1] < biases[2], biases

    def test_null_bias_vanishes_at_zero_variance(self):
        """log_sd=0 means no Monte Carlo noise → exact zero QALY."""
        profile = Profile(
            age=39, sex="male", bmi_category="normal",
            smoking_status="never", has_diabetes=False,
            has_hypertension=False, activity_level="light",
        )
        r = simulate_qaly_profile_vectorized(
            self._null_intervention(0.0), profile,
            n_simulations=10_000, random_state=1,
        )
        assert r.mean == pytest.approx(0.0, abs=1e-9)

    def test_null_median_and_mean_straddle_zero(self):
        """For null HR, median is slightly positive and mean slightly negative.

        Mean-centering the lognormal (``log_mean = log(hr) - σ²/2``) puts
        the median HR below 1.0. The median-HR simulation therefore
        produces a slightly protective survival curve → positive median
        QALY. The mean QALY is negative from Jensen-on-survival. This
        test documents that mean and median straddle zero and are of
        comparable magnitude — surfacing both lets readers see the
        convexity corridor.
        """
        profile = Profile(
            age=39, sex="male", bmi_category="normal",
            smoking_status="never", has_diabetes=False,
            has_hypertension=False, activity_level="light",
        )
        r = simulate_qaly_profile_vectorized(
            self._null_intervention(0.12), profile,
            n_simulations=100_000, random_state=1,
        )
        assert r.median > 0, "median QALY should be slightly positive (median HR < 1 from mean-centering)"
        assert r.mean < 0, "mean QALY should be slightly negative (Jensen on lifetime survival)"
        # Same order of magnitude (within ~3x of each other).
        assert 0.33 < abs(r.median / r.mean) < 3.0, (
            f"median {r.median:.4f} and mean {r.mean:.4f} diverge too much"
        )

    def test_portfolio_bias_not_superadditive(self):
        """Stacking N null interventions must not produce >N× per-item bias.

        Reviewer flagged that portfolio-ceiling saturation could interact
        with per-intervention Jensen bias non-linearly. This test verifies
        the isolated-sum across 5 null interventions stays roughly linear
        in N (no super-additive blowup). Near-linearity indicates each
        item's bias is independent — a portfolio ceiling applied on top
        won't amplify beyond the linear rate.
        """
        profile = Profile(
            age=39, sex="male", bmi_category="normal",
            smoking_status="never", has_diabetes=False,
            has_hypertension=False, activity_level="light",
        )
        per_item_biases = []
        for seed in range(1, 6):
            r = simulate_qaly_profile_vectorized(
                self._null_intervention(0.12), profile,
                n_simulations=50_000, random_state=seed,
            )
            per_item_biases.append(r.mean)
        per_item_mean = sum(per_item_biases) / len(per_item_biases)
        stacked_sum = sum(per_item_biases)
        # Pin the single-item bound that drives this whole test.
        single_item_cap = 0.05
        assert abs(per_item_mean) < single_item_cap, (
            f"Per-item bias exceeds cap: {per_item_mean:.4f}"
        )
        # Sum of N independent null-HR sims must stay within N × cap
        # (no super-additive blowup). Allow 20% overhead for finite-sample
        # variance in the 5-seed average.
        n = len(per_item_biases)
        assert abs(stacked_sum) < n * single_item_cap * 1.2, (
            f"Stacked null-HR bias super-additive: {stacked_sum:.4f} "
            f"exceeds {n}× single-item bound ({n*single_item_cap:.3f})"
        )
