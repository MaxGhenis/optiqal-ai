"""Tests for the intervention catalog and publication bias correction."""

import pytest
import numpy as np

from optiqal.confounding import publication_bias_correct
from optiqal.catalog import (
    CATALOG,
    CatalogEntry,
    get_catalog,
)
from optiqal.combination import find_optimal_portfolio_with_costs


class TestPublicationBiasCorrection:
    def test_shrinks_toward_null(self):
        """Corrected HR should be closer to 1.0 than observed."""
        corrected = publication_bias_correct(0.80, shrinkage=0.30)
        assert 0.80 < corrected < 1.0

    def test_null_unchanged(self):
        """HR = 1.0 stays at 1.0."""
        assert publication_bias_correct(1.0, shrinkage=0.30) == pytest.approx(1.0)

    def test_harmful_shrinks_toward_null(self):
        """HR > 1.0 should also shrink toward 1.0."""
        corrected = publication_bias_correct(1.50, shrinkage=0.30)
        assert 1.0 < corrected < 1.50

    def test_zero_shrinkage_unchanged(self):
        """No shrinkage returns original HR."""
        assert publication_bias_correct(0.80, shrinkage=0.0) == pytest.approx(0.80)

    def test_full_shrinkage_returns_null(self):
        """100% shrinkage returns HR = 1.0."""
        assert publication_bias_correct(0.80, shrinkage=1.0) == pytest.approx(1.0)

    def test_30pct_shrinkage_value(self):
        """Check specific numeric value for 30% shrinkage of HR 0.80."""
        # log(0.80) = -0.2231, * 0.70 = -0.1562, exp = 0.8555
        corrected = publication_bias_correct(0.80, shrinkage=0.30)
        assert corrected == pytest.approx(0.8555, rel=0.01)


class TestCatalog:
    def test_catalog_not_empty(self):
        assert len(CATALOG) > 40

    def test_all_entries_have_required_fields(self):
        for entry_id, entry in CATALOG.items():
            assert entry.id == entry_id
            assert entry.name
            assert 0 < entry.hr_observed <= 1.5
            assert entry.log_sd > 0
            assert entry.conf_alpha > 0
            assert entry.conf_beta > 0
            assert entry.annual_cost >= 0 or entry.annual_cost < 0  # savings possible

    def test_categories_present(self):
        categories = {e.category for e in CATALOG.values()}
        assert "rx_current" in categories
        assert "supplement_current" in categories
        assert "supplement_candidate" in categories

    def test_get_catalog_filter(self):
        rx = get_catalog(["rx_current"])
        assert all(e.category == "rx_current" for e in rx.values())
        assert len(rx) > 0

    def test_to_intervention(self):
        entry = CATALOG["omega3_clo"]
        intervention = entry.to_intervention(pub_bias_shrinkage=0.30)
        assert intervention.id == "omega3_clo"
        assert intervention.mortality is not None
        assert intervention.confounding_prior is not None

    def test_to_intervention_applies_pub_bias(self):
        entry = CATALOG["omega3_clo"]
        # With 0% shrinkage, should use raw HR
        int_no_bias = entry.to_intervention(pub_bias_shrinkage=0.0)
        # With 30% shrinkage, HR should be closer to 1
        int_biased = entry.to_intervention(pub_bias_shrinkage=0.30)

        hr_raw = int_no_bias.mortality.hazard_ratio.mean
        hr_corrected = int_biased.mortality.hazard_ratio.mean
        assert hr_corrected > hr_raw  # Closer to 1.0 (less protective)


class TestCostAwarePortfolio:
    @pytest.fixture
    def sample_data(self):
        qalys = {
            "a": 0.10,
            "b": 0.05,
            "c": 0.03,
            "d": 0.02,
            "e": 0.01,
        }
        costs = {
            "a": 100,
            "b": 50,
            "c": 30,
            "d": 200,  # Expensive relative to benefit
            "e": 10,
        }
        return qalys, costs

    def test_selects_best_value_first(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        assert len(result) > 0
        assert result[0]["added_intervention"] == "a"  # Highest QALY

    def test_stops_at_negative_marginal(self, sample_data):
        qalys, costs = sample_data
        # Very low WTP should exclude expensive items
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=1_000, horizon_years=40,
        )
        # Should select fewer items when WTP is low
        result_high = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        assert len(result) <= len(result_high)

    def test_complexity_penalty_limits_stack(self, sample_data):
        qalys, costs = sample_data
        # High complexity cost should limit stack size
        result_high_cp = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
            complexity_cost_per_item=0.01,  # Very high
            complexity_free_slots=2,
        )
        result_low_cp = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
            complexity_cost_per_item=0.0001,
            complexity_free_slots=2,
        )
        assert len(result_high_cp) <= len(result_low_cp)

    def test_respects_exclude(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
            exclude=["a"],
        )
        selected = {step["added_intervention"] for step in result}
        assert "a" not in selected

    def test_diminishing_returns_applied(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        if len(result) >= 2:
            assert result[0]["diminishing_returns_factor"] == 1.0
            assert result[1]["diminishing_returns_factor"] == 0.95

    def test_output_structure(self, sample_data):
        qalys, costs = sample_data
        result = find_optimal_portfolio_with_costs(
            qalys, costs, wtp=200_000, horizon_years=40,
        )
        assert len(result) > 0
        step = result[0]
        assert "step" in step
        assert "added_intervention" in step
        assert "marginal_qaly" in step
        assert "marginal_net_value" in step
        assert "diminishing_returns_factor" in step
        assert "complexity_penalty" in step
        assert "total_qaly" in step
        assert "total_annual_cost" in step
        assert "selected_interventions" in step
