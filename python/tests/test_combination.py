"""Tests for intervention combination module."""

import pytest
import sys
sys.path.insert(0, 'python')

from optiqal.combination import (
    get_overlap_factor,
    get_diminishing_returns_factor,
    estimate_combined_qaly_from_singles,
    find_optimal_portfolio_from_qalys,
    OVERLAP_MATRIX,
)


class TestOverlapFactors:
    """Test overlap factor lookup."""

    def test_known_overlap(self):
        """Walking and exercise have known overlap."""
        overlap = get_overlap_factor("walking_30min_daily", "daily_exercise_moderate")
        assert overlap == 0.4

    def test_symmetric_overlap(self):
        """Overlap should be symmetric."""
        ab = get_overlap_factor("walking_30min_daily", "daily_exercise_moderate")
        ba = get_overlap_factor("daily_exercise_moderate", "walking_30min_daily")
        assert ab == ba

    def test_no_overlap_returns_one(self):
        """Non-overlapping interventions return 1.0."""
        overlap = get_overlap_factor("mediterranean_diet", "meditation_daily")
        assert overlap == 1.0

    def test_diet_supplement_overlap(self):
        """Mediterranean diet and fish oil have overlap."""
        overlap = get_overlap_factor("mediterranean_diet", "fish_oil_supplement")
        assert overlap == 0.5


class TestDiminishingReturns:
    """Test diminishing returns factor."""

    def test_single_intervention_no_penalty(self):
        """Single intervention has no penalty."""
        assert get_diminishing_returns_factor(1) == 1.0

    def test_two_interventions_small_penalty(self):
        """Two interventions have small penalty."""
        factor = get_diminishing_returns_factor(2)
        assert 0.9 < factor < 1.0

    def test_many_interventions_floor(self):
        """Many interventions hit floor at 0.80."""
        assert get_diminishing_returns_factor(10) == 0.80
        assert get_diminishing_returns_factor(20) == 0.80

    def test_monotonically_decreasing(self):
        """Factor decreases with more interventions."""
        factors = [get_diminishing_returns_factor(n) for n in range(1, 10)]
        for i in range(len(factors) - 1):
            assert factors[i] >= factors[i + 1]


class TestCombinedQalyEstimation:
    """Test QALY combination with overlap and diminishing returns."""

    @pytest.fixture
    def sample_qalys(self):
        """Sample single-intervention QALYs."""
        return {
            "walking_30min_daily": 0.15,
            "daily_exercise_moderate": 0.35,
            "mediterranean_diet": 0.50,
            "meditation_daily": 0.10,
            "fish_oil_supplement": 0.06,
        }

    def test_single_intervention_unchanged(self, sample_qalys):
        """Single intervention returns exact value."""
        result = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["mediterranean_diet"]
        )
        assert result == pytest.approx(0.50, rel=0.01)

    def test_non_overlapping_near_additive(self, sample_qalys):
        """Non-overlapping interventions are nearly additive."""
        result = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["mediterranean_diet", "meditation_daily"]
        )
        simple_sum = 0.50 + 0.10
        # Should be close but slightly less due to diminishing returns
        assert result < simple_sum
        assert result > simple_sum * 0.9

    def test_overlapping_reduced(self, sample_qalys):
        """Overlapping interventions are reduced."""
        result = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["walking_30min_daily", "daily_exercise_moderate"]
        )
        simple_sum = 0.15 + 0.35
        # Should be significantly less due to 0.4 overlap
        assert result < simple_sum * 0.8

    def test_order_matters_for_overlap(self, sample_qalys):
        """Order affects which intervention gets overlap penalty - higher value first is better."""
        # Walking first, exercise second: exercise (higher) gets penalty
        walking_first = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["walking_30min_daily", "daily_exercise_moderate"]
        )
        # Exercise first, walking second: walking (lower) gets penalty
        exercise_first = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["daily_exercise_moderate", "walking_30min_daily"]
        )
        # Exercise first is better because the penalty is on the smaller value
        assert exercise_first > walking_first

    def test_no_overlap_option(self, sample_qalys):
        """Can disable overlap correction."""
        with_overlap = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["walking_30min_daily", "daily_exercise_moderate"],
            apply_overlap=True
        )
        without_overlap = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["walking_30min_daily", "daily_exercise_moderate"],
            apply_overlap=False
        )
        assert without_overlap > with_overlap

    def test_no_diminishing_returns_option(self, sample_qalys):
        """Can disable diminishing returns."""
        all_ids = list(sample_qalys.keys())
        with_dr = estimate_combined_qaly_from_singles(
            sample_qalys,
            all_ids,
            apply_diminishing_returns=True
        )
        without_dr = estimate_combined_qaly_from_singles(
            sample_qalys,
            all_ids,
            apply_diminishing_returns=False
        )
        assert without_dr > with_dr


class TestOptimalPortfolio:
    """Test optimal portfolio selection."""

    @pytest.fixture
    def sample_qalys(self):
        """Sample single-intervention QALYs."""
        return {
            "mediterranean_diet": 0.50,
            "daily_exercise_moderate": 0.35,
            "walking_30min_daily": 0.15,
            "meditation_daily": 0.10,
            "sleep_8_hours": 0.08,
        }

    def test_highest_first(self, sample_qalys):
        """First selection is highest single QALY."""
        portfolio = find_optimal_portfolio_from_qalys(sample_qalys, max_interventions=1)
        assert len(portfolio) == 1
        assert portfolio[0]["added_intervention"] == "mediterranean_diet"

    def test_respects_max_interventions(self, sample_qalys):
        """Respects max_interventions limit."""
        portfolio = find_optimal_portfolio_from_qalys(sample_qalys, max_interventions=2)
        assert len(portfolio) == 2

    def test_respects_exclusions(self, sample_qalys):
        """Excluded interventions are not selected."""
        portfolio = find_optimal_portfolio_from_qalys(
            sample_qalys,
            exclude=["mediterranean_diet"]
        )
        for step in portfolio:
            assert step["added_intervention"] != "mediterranean_diet"

    def test_marginal_qaly_decreasing(self, sample_qalys):
        """Marginal QALY generally decreases (with possible exceptions from overlap)."""
        portfolio = find_optimal_portfolio_from_qalys(sample_qalys, max_interventions=5)
        # First should always have highest marginal
        assert portfolio[0]["marginal_qaly"] >= portfolio[1]["marginal_qaly"]

    def test_total_qaly_increasing(self, sample_qalys):
        """Total QALY always increases."""
        portfolio = find_optimal_portfolio_from_qalys(sample_qalys, max_interventions=5)
        totals = [step["total_qaly"] for step in portfolio]
        for i in range(len(totals) - 1):
            assert totals[i] < totals[i + 1]

    def test_walking_after_exercise_due_to_overlap(self, sample_qalys):
        """Walking comes after other interventions due to exercise overlap."""
        portfolio = find_optimal_portfolio_from_qalys(sample_qalys, max_interventions=5)

        # Find positions
        positions = {step["added_intervention"]: step["step"] for step in portfolio}

        # Exercise should come before walking (higher raw QALY, no prior overlap)
        assert positions.get("daily_exercise_moderate", 99) < positions.get("walking_30min_daily", 99)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
