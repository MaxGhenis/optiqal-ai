"""Tests for the end-to-end analyzer."""

import pytest

from optiqal import (
    Profile,
    AnalysisConfig,
    AnalysisResult,
    Decision,
    analyze,
    format_full_report,
    CATALOG,
    BUNDLES,
)


@pytest.fixture
def config():
    return AnalysisConfig(
        profile=Profile(
            age=39, sex="male", bmi_category="normal",
            smoking_status="never", has_diabetes=False,
            has_hypertension=False, activity_level="light",
        ),
        n_simulations=5_000,  # Fewer for speed in tests
    )


class TestAnalyze:
    def test_basic_analysis(self, config):
        result = analyze(config)
        assert isinstance(result, AnalysisResult)
        assert len(result.item_results) > 40
        assert len(result.portfolio) > 0
        assert len(result.selected_ids) > 0

    def test_item_results_structure(self, config):
        result = analyze(config)
        r = result.item_results[0]
        assert "id" in r
        assert "name" in r
        assert "total_qaly" in r
        assert "days" in r
        assert "gross_value" in r
        assert "annual_cost" in r

    def test_portfolio_stops_at_positive(self, config):
        result = analyze(config)
        for step in result.portfolio:
            assert step["marginal_net_value"] > 0

    def test_bundle_recommendations(self, config):
        result = analyze(config)
        assert len(result.bundle_recommendations) > 0
        for b in result.bundle_recommendations:
            assert "bundle_name" in b
            assert "worth_it" in b
            assert "net_value" in b

    def test_category_filter(self, config):
        config.categories = ["rx_current"]
        result = analyze(config)
        for r in result.item_results:
            assert r["category"] == "rx_current"

    def test_selected_ids_property(self, config):
        result = analyze(config)
        ids = result.selected_ids
        assert isinstance(ids, list)
        assert all(isinstance(i, str) for i in ids)

    def test_total_cost_property(self, config):
        result = analyze(config)
        assert result.total_annual_cost >= 0

    def test_total_days_property(self, config):
        result = analyze(config)
        assert result.total_days > 0


class TestDecisions:
    def test_add_decision(self, config):
        result = analyze(
            config,
            decisions=[
                Decision("add", "glycine_2g", "ADD: Glycine 2g ($40/yr)"),
            ],
        )
        assert result.decisions is not None
        assert len(result.decisions) == 1
        d = result.decisions[0]
        assert d["decision_type"] == "add"
        assert d["verdict"] in ("DO IT", "MARGINAL", "SKIP")
        assert "net_value" in d
        assert "days" in d
        assert "ci_low" in d
        assert "ci_high" in d

    def test_drop_decision(self, config):
        result = analyze(
            config,
            decisions=[
                Decision("drop", "collagen_22g", "DROP: Collagen 22g (saves $360/yr)"),
            ],
        )
        d = result.decisions[0]
        assert d["annual_cost"] < 0  # Savings
        assert d["decision_type"] == "drop"

    def test_adjust_decision(self, config):
        result = analyze(
            config,
            decisions=[
                Decision(
                    "adjust", "melatonin_300mcg",
                    "ADJUST: Melatonin 1.5mg→300mcg",
                    override_hr=0.998,
                    override_cost=0,
                    override_qol=0.002,
                ),
            ],
        )
        d = result.decisions[0]
        assert d["decision_type"] == "adjust"

    def test_multiple_decisions_sorted(self, config):
        result = analyze(
            config,
            decisions=[
                Decision("add", "glycine_2g", "ADD: Glycine"),
                Decision("drop", "collagen_22g", "DROP: Collagen"),
                Decision("add", "apigenin_50", "ADD: Apigenin"),
            ],
        )
        assert len(result.decisions) == 3
        # Should be sorted by net_value descending
        values = [d["net_value"] for d in result.decisions]
        assert values == sorted(values, reverse=True)

    def test_unknown_item_raises(self, config):
        with pytest.raises(ValueError, match="Unknown"):
            analyze(
                config,
                decisions=[Decision("add", "nonexistent_item", "ADD: Nothing")],
            )


class TestReport:
    def test_format_full_report(self, config):
        result = analyze(config)
        report = format_full_report(result)
        assert isinstance(report, str)
        assert "OPTIQAL" in report
        assert "GREEDY PORTFOLIO" in report
        assert "EXCLUDED" in report
        assert "BY CATEGORY" in report
        assert "BUNDLE" in report

    def test_report_with_decisions(self, config):
        result = analyze(
            config,
            decisions=[
                Decision("add", "glycine_2g", "ADD: Glycine 2g"),
                Decision("drop", "collagen_22g", "DROP: Collagen 22g"),
            ],
        )
        report = format_full_report(result)
        assert "DECISION ANALYSIS" in report
        assert "RECOMMENDATION SUMMARY" in report
        assert "DO IT" in report or "MARGINAL" in report or "SKIP" in report


class TestBundles:
    def test_bundles_defined(self):
        assert len(BUNDLES) >= 4
        assert "blueprint_essential_capsules" in BUNDLES

    def test_bundle_items_in_catalog(self):
        for bundle in BUNDLES.values():
            for item_id in bundle.item_ids:
                assert item_id in CATALOG, (
                    f"Bundle {bundle.id} references unknown item {item_id}"
                )
