"""Tests for intervention combination module."""

import pytest
import sys
sys.path.insert(0, 'python')

from optiqal.combination import (
    get_overlap_factor,
    estimate_combined_qaly_from_singles,
    find_optimal_portfolio_from_qalys,
    find_optimal_portfolio_with_costs,
    rank_interventions_by_marginal_cost_per_qaly,
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


class TestCombinedQalyEstimation:
    """Test QALY combination with overlap."""

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
        """Non-overlapping interventions are additive."""
        result = estimate_combined_qaly_from_singles(
            sample_qalys,
            ["mediterranean_diet", "meditation_daily"]
        )
        simple_sum = 0.50 + 0.10
        assert result == pytest.approx(simple_sum)

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


class TestMarginalCostEffectivenessRanking:
    """Test threshold-free marginal cost-effectiveness ordering."""

    def test_orders_by_lowest_marginal_cost_per_qaly_first(self):
        ranking = rank_interventions_by_marginal_cost_per_qaly(
            single_qalys={"a": 1.0, "b": 0.5, "c": 0.2},
            annual_costs={"a": 100_000, "b": 10_000, "c": 1_000},
            cost_values={"a": 100_000, "b": 10_000, "c": 1_000},
        )

        assert [step["added_intervention"] for step in ranking] == ["c", "b", "a"]
        assert ranking[0]["marginal_cost_per_qaly"] == pytest.approx(5_000)
        assert ranking[1]["marginal_cost_per_qaly"] == pytest.approx(20_000)
        assert ranking[2]["marginal_cost_per_qaly"] == pytest.approx(100_000)

    def test_shared_product_zero_marginal_cost_moves_second_item_up(self):
        def marginal_cost_value(selected_ids, candidate_id):
            if candidate_id == "b" and "a" in selected_ids:
                return 0.0
            return {"a": 1_000.0, "b": 1_000.0, "c": 30_000.0}[candidate_id]

        ranking = rank_interventions_by_marginal_cost_per_qaly(
            single_qalys={"a": 0.1, "b": 0.05, "c": 0.2},
            annual_costs={"a": 100, "b": 100, "c": 100},
            cost_values={"a": 1_000, "b": 1_000, "c": 30_000},
            marginal_cost_value_fn=marginal_cost_value,
        )

        assert [step["added_intervention"] for step in ranking] == ["a", "b", "c"]
        assert ranking[1]["marginal_cost_per_qaly"] == pytest.approx(0.0)

    def test_stops_when_remaining_marginal_qaly_is_nonpositive(self):
        def stack_penalty(item_ids):
            return -0.2 if set(item_ids) == {"a", "b"} else 0.0

        ranking = rank_interventions_by_marginal_cost_per_qaly(
            single_qalys={"a": 0.1, "b": 0.05},
            annual_costs={"a": 100, "b": 100},
            cost_values={"a": 100, "b": 100},
            stack_interaction_penalty_fn=stack_penalty,
        )

        assert [step["added_intervention"] for step in ranking] == ["a"]

    def test_respects_exclusive_groups(self):
        ranking = rank_interventions_by_marginal_cost_per_qaly(
            single_qalys={"hiit_1": 0.01, "hiit_2": 0.02, "c": 0.005},
            annual_costs={"hiit_1": 0, "hiit_2": 0, "c": 100},
            cost_values={"hiit_1": 0, "hiit_2": 0, "c": 100},
            exclusive_groups={"hiit_1": "hiit", "hiit_2": "hiit"},
        )

        assert [step["added_intervention"] for step in ranking] == ["hiit_2", "c"]

    def test_preselected_state_changes_conditional_ranking(self):
        ranking = rank_interventions_by_marginal_cost_per_qaly(
            single_qalys={"a": 0.10, "b": 0.06, "c": 0.03},
            annual_costs={"a": 100, "b": 500, "c": 50},
            cost_values={"a": 100, "b": 500, "c": 50},
            preselected=["a"],
        )

        assert [step["added_intervention"] for step in ranking] == ["c", "b"]
        assert ranking[0]["preselected_interventions"] == ["a"]
        assert ranking[0]["selected_interventions"] == ["a", "c"]

    def test_preselected_exclusive_group_blocks_other_members(self):
        ranking = rank_interventions_by_marginal_cost_per_qaly(
            single_qalys={"traz": 0.02, "dora": 0.03, "mel": 0.01},
            annual_costs={"traz": 100, "dora": 1000, "mel": 20},
            cost_values={"traz": 100, "dora": 1000, "mel": 20},
            preselected=["traz"],
            exclusive_groups={"traz": "insomnia", "dora": "insomnia"},
        )

        assert [step["added_intervention"] for step in ranking] == ["mel"]

    def test_preselected_stack_uses_max_additions_not_total_size(self):
        ranking = rank_interventions_by_marginal_cost_per_qaly(
            single_qalys={"base1": 0.01, "base2": 0.01, "base3": 0.01, "a": 0.05, "b": 0.02},
            annual_costs={"base1": 10, "base2": 10, "base3": 10, "a": 50, "b": 20},
            cost_values={"base1": 10, "base2": 10, "base3": 10, "a": 50, "b": 20},
            preselected=["base1", "base2", "base3"],
            max_interventions=2,
        )

        assert [step["added_intervention"] for step in ranking] == ["b", "a"]
        assert ranking[-1]["selected_interventions"] == ["base1", "base2", "base3", "b", "a"]


class TestCostAwarePortfolioWithPreselectedState:
    def test_preselected_stack_uses_max_additions_not_total_size(self):
        portfolio = find_optimal_portfolio_with_costs(
            single_qalys={"base1": 0.01, "base2": 0.01, "base3": 0.01, "a": 0.05, "b": 0.02},
            annual_costs={"base1": 10, "base2": 10, "base3": 10, "a": 50, "b": 20},
            cost_values={"base1": 10, "base2": 10, "base3": 10, "a": 50, "b": 20},
            wtp=10_000,
            preselected=["base1", "base2", "base3"],
            max_interventions=2,
        )

        assert [step["added_intervention"] for step in portfolio] == ["a", "b"]
        assert portfolio[-1]["selected_interventions"] == ["base1", "base2", "base3", "a", "b"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
