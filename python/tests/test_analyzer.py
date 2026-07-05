"""Tests for the end-to-end analyzer."""

import pytest

from optiqal import (
    BUNDLES,
    CATALOG,
    AnalysisConfig,
    AnalysisResult,
    Decision,
    Profile,
    analyze,
    format_full_report,
    serialize_item_results,
)
from optiqal.catalog import CatalogEntry
from optiqal.intervention import Distribution, InteractionRule
from optiqal.sleep import SleepMetrics


@pytest.fixture
def config():
    return AnalysisConfig(
        profile=Profile(
            age=39,
            sex="male",
            bmi_category="normal",
            smoking_status="never",
            has_diabetes=False,
            has_hypertension=False,
            activity_level="light",
        ),
        n_simulations=5_000,  # Fewer for speed in tests
    )


class TestAnalyze:
    def test_qaly_discount_default_matches_app(self, config):
        assert config.qaly_discount_rate == pytest.approx(0.03)

    def test_analysis_config_has_no_complexity_penalty(self, config):
        assert not hasattr(config, "complexity_cost_per_item")
        assert not hasattr(config, "complexity_free_slots")

    def test_qaly_discount_sensitivity_rate_allowed(self):
        config = AnalysisConfig(
            profile=Profile(
                age=39,
                sex="male",
                bmi_category="normal",
                smoking_status="never",
                has_diabetes=False,
                has_hypertension=False,
                activity_level="light",
            ),
            qaly_discount_rate=0.015,
        )

        assert config.qaly_discount_rate == pytest.approx(0.015)

    def test_negative_qaly_discount_rejected(self):
        with pytest.raises(ValueError, match="nonnegative"):
            AnalysisConfig(
                profile=Profile(
                    age=39,
                    sex="male",
                    bmi_category="normal",
                    smoking_status="never",
                    has_diabetes=False,
                    has_hypertension=False,
                    activity_level="light",
                ),
                qaly_discount_rate=-0.01,
            )

    def test_analysis_config_derives_sleep_estimate_from_metrics(self):
        config = AnalysisConfig(
            profile=Profile(
                age=39,
                sex="male",
                bmi_category="normal",
                smoking_status="never",
                has_diabetes=False,
                has_hypertension=False,
                activity_level="light",
            ),
            sleep_metrics=SleepMetrics(
                duration_hours=6.4,
                recovery_score=52.0,
                sleep_quality_score=76.0,
                waso_min=18.0,
                routine_score=68.0,
                social_jetlag_min=55.0,
                latency_min=23.0,
                breathing_score=0.75,
                spo2=95.0,
                snore_pct=4.0,
                sleep_debt_min=70.0,
            ),
        )

        assert config.sleep_estimate is not None
        assert config.sleep_estimate.annual_qaly_loss > 0
        assert config.sleep_overlap_multipliers is not None
        assert config.sleep_overlap_multipliers["sleep_duration_support"] < 1.0

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
        assert "harm_qaly" in r
        assert "days" in r
        assert "gross_value" in r
        assert "annual_cost" in r
        assert "sleep_qol_qaly" in r
        assert "component_breakdown" in r
        assert "top_positive_component" in r
        assert "top_negative_component" in r

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

    def test_custom_catalog_interaction_penalty_affects_portfolio(self, config):
        sedation_rule = InteractionRule(
            id="sedation_stack",
            requires_tags=["sedating"],
            minimum_matches=2,
            description="Custom sedation penalty.",
            annual_qaly_loss=Distribution(type="point", params={"value": 0.01}),
        )
        custom_catalog = {
            "sleep_a": CatalogEntry(
                id="sleep_a",
                name="Sleep A",
                category="supplement_current",
                hr_observed=1.0,
                log_sd=0.05,
                conf_alpha=1.0,
                conf_beta=1.0,
                annual_cost=0,
                qol_annual=0.005,
                interaction_tags=["sedating"],
                interaction_rules=[sedation_rule],
            ),
            "sleep_b": CatalogEntry(
                id="sleep_b",
                name="Sleep B",
                category="supplement_current",
                hr_observed=1.0,
                log_sd=0.05,
                conf_alpha=1.0,
                conf_beta=1.0,
                annual_cost=0,
                qol_annual=0.005,
                interaction_tags=["sedating"],
                interaction_rules=[sedation_rule],
            ),
        }

        result = analyze(config, catalog_entries=custom_catalog)

        assert len(result.item_results) == 2
        assert len(result.selected_ids) == 1
        assert result.selected_ids[0] in custom_catalog

    def test_product_cost_callbacks_flow_through_analyze(self, config):
        custom_catalog = {
            "a": CatalogEntry(
                id="a",
                name="A",
                category="supplement_current",
                hr_observed=1.0,
                log_sd=0.05,
                conf_alpha=1.0,
                conf_beta=1.0,
                annual_cost=100,
                qol_annual=0.003,
            ),
            "b": CatalogEntry(
                id="b",
                name="B",
                category="supplement_current",
                hr_observed=1.0,
                log_sd=0.05,
                conf_alpha=1.0,
                conf_beta=1.0,
                annual_cost=100,
                qol_annual=0.0015,
            ),
        }

        def marginal_cost_value_fn(selected, candidate):
            if candidate == "b" and "a" in selected:
                return 0.0
            return 4_000.0

        def total_annual_cost_fn(selected):
            return 100.0 if selected else 0.0

        result = analyze(
            config,
            catalog_entries=custom_catalog,
            marginal_cost_value_fn=marginal_cost_value_fn,
            total_annual_cost_fn=total_annual_cost_fn,
        )

        assert result.selected_ids == ["a", "b"]
        assert result.total_annual_cost == pytest.approx(100.0)


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
                    "adjust",
                    "melatonin_300mcg",
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


class TestReportSerialization:
    def test_serialize_item_results_supports_enrichment(self):
        entry = CatalogEntry(
            id="sleep_item",
            name="Sleep Item",
            category="sleep_candidate",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=120,
            qol_annual=0.003,
            notes="Test note",
            sources=["https://example.com"],
        )

        rows = serialize_item_results(
            [{"id": "sleep_item"}],
            effective_results_by_id={
                "sleep_item": {
                    "id": "sleep_item",
                    "hr_corrected": 0.99,
                    "days": 2.25,
                    "p_benefit": 0.7,
                    "p_harm": 0.1,
                    "gross_value": 800.4,
                    "harm_qaly": 0.0002,
                    "direct_harm_qaly": 0.0001,
                    "interaction_harm_qaly": 0.0,
                    "raw_qol_qaly": 0.0015,
                    "qol_qaly": 0.0012,
                    "raw_sleep_qol_annual": 0.0005,
                    "sleep_qol_annual": 0.0004,
                    "raw_sleep_qol_qaly": 0.001,
                    "sleep_qol_qaly": 0.0008,
                    "evidence_discount_qaly": 0.0005,
                    "component_breakdown": {
                        "mortality_qaly": 0.0,
                        "direct_qol_qaly": 0.0012,
                        "sleep_qol_qaly": 0.0008,
                        "direct_harm_qaly": 0.0001,
                        "interaction_harm_qaly": 0.0,
                        "evidence_discount_qaly": -0.0005,
                    },
                    "top_positive_component": "direct_qol_qaly",
                    "top_negative_component": "evidence_discount_qaly",
                    "sleep_mortality_relief_fraction": 0.15,
                    "sleep_mortality_hr_multiplier": 0.995,
                    "cost_per_qaly": 123456.7,
                    "qaly_source": "ground_up",
                    "range_low_qaly": 0.001,
                    "range_high_qaly": 0.003,
                    "within_range": True,
                    "ground_up_rationale": "because",
                    "ground_up_personalization": "for profile",
                    "ground_up_sources": ["https://ground-up.example"],
                }
            },
            catalog_entries={"sleep_item": entry},
            selected_ids=["sleep_item"],
            category_labels={"sleep_candidate": "Sleep interventions"},
            status_labels={"sleep_candidate": "watching"},
            evidence_confidence_for_entry=lambda _entry: "medium",
            row_enricher=lambda row: row.update({"db_product": "DB Item"}),
        )

        assert len(rows) == 1
        row = rows[0]
        assert row["name"] == "Sleep Item"
        assert row["category_label"] == "Sleep interventions"
        assert row["status"] == "watching"
        assert row["in_portfolio"] is True
        assert row["cost_per_qaly"] == 123457
        assert row["db_product"] == "DB Item"
        assert row["component_breakdown"]["evidence_discount_qaly"] == -0.0005
        assert row["top_positive_component"] == "direct_qol_qaly"
        assert row["top_negative_component"] == "evidence_discount_qaly"


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
