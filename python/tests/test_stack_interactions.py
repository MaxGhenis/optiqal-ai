"""Tests for stack-level interaction penalties."""

import pytest

from optiqal.catalog import CatalogEntry
from optiqal.intervention import Distribution, InteractionRule

from optiqal import CATALOG, Profile
from optiqal.stack_interactions import expected_stack_interaction_qaly


def _profile() -> Profile:
    return Profile(
        age=39,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="light",
    )


def test_bleeding_stack_penalty_triggers_once():
    penalty, details = expected_stack_interaction_qaly(
        item_ids=["omega3_clo", "garlic_1200", "ginger_400"],
        catalog_entries=CATALOG,
        profile=_profile(),
    )

    assert penalty < 0
    assert [detail["id"] for detail in details] == ["bleeding_stack"]


def test_duplicate_vitamin_d_penalty_uses_extra_tags():
    penalty, details = expected_stack_interaction_qaly(
        item_ids=["vitamin_d_2000"],
        catalog_entries=CATALOG,
        profile=_profile(),
        extra_tags=["vitamin_d"],
    )

    assert penalty < 0
    assert [detail["id"] for detail in details] == ["duplicate_vitamin_d"]


def test_stack_penalty_uses_rule_active_year_window():
    sedation_rule = InteractionRule(
        id="sedation_stack",
        requires_tags=["sedating"],
        minimum_matches=2,
        annual_qaly_loss=Distribution(type="point", params={"value": 0.01}),
    )
    catalog = {
        "a": CatalogEntry(
            id="a",
            name="A",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            interaction_tags=["sedating"],
            interaction_rules=[sedation_rule],
        ),
        "b": CatalogEntry(
            id="b",
            name="B",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            interaction_tags=["sedating"],
            interaction_rules=[sedation_rule],
        ),
    }

    penalty, details = expected_stack_interaction_qaly(
        item_ids=["a", "b"],
        catalog_entries=catalog,
        profile=_profile(),
        item_active_years={"a": 1.0, "b": 4.0},
    )

    assert details[0]["active_years"] == 1.0
    assert penalty == pytest.approx(-0.01, rel=0.05)


def test_benefit_overlap_penalty_shrinks_same_domain_items():
    catalog = {
        "a": CatalogEntry(
            id="a",
            name="A",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_quality_support"],
        ),
        "b": CatalogEntry(
            id="b",
            name="B",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_quality_support"],
        ),
    }

    penalty, details = expected_stack_interaction_qaly(
        item_ids=["a", "b"],
        catalog_entries=catalog,
        profile=_profile(),
        item_qalys={"a": 0.04, "b": 0.03},
    )

    assert penalty == pytest.approx(-0.0135)
    assert [detail["id"] for detail in details] == ["benefit_overlap:sleep_quality_support"]
    assert details[0]["matched_tag_count"] == 2
    assert details[0]["item_ids"] == ["b"]


def test_disjoint_sleep_components_do_not_overlap():
    catalog = {
        "a": CatalogEntry(
            id="a",
            name="A",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_quality_support"],
        ),
        "b": CatalogEntry(
            id="b",
            name="B",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_regularity_support"],
        ),
    }

    penalty, details = expected_stack_interaction_qaly(
        item_ids=["a", "b"],
        catalog_entries=catalog,
        profile=_profile(),
        item_qalys={"a": 0.04, "b": 0.03},
    )

    assert penalty == pytest.approx(0.0)
    assert details == []


def test_benefit_overlap_multiplier_can_reduce_penalty():
    catalog = {
        "a": CatalogEntry(
            id="a",
            name="A",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_quality_support"],
        ),
        "b": CatalogEntry(
            id="b",
            name="B",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_quality_support"],
        ),
    }

    penalty, _ = expected_stack_interaction_qaly(
        item_ids=["a", "b"],
        catalog_entries=catalog,
        profile=_profile(),
        item_qalys={"a": 0.04, "b": 0.03},
        benefit_tag_multipliers={"sleep_quality_support": 0.5},
    )

    assert penalty == pytest.approx(-0.00675)


def test_benefit_overlap_respects_shared_active_window():
    catalog = {
        "short": CatalogEntry(
            id="short",
            name="Short high-intensity benefit",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_quality_support"],
        ),
        "long": CatalogEntry(
            id="long",
            name="Long lower-intensity benefit",
            category="supplement_current",
            hr_observed=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=1.0,
            annual_cost=0,
            benefit_tags=["sleep_quality_support"],
        ),
    }

    old_penalty, _ = expected_stack_interaction_qaly(
        item_ids=["short", "long"],
        catalog_entries=catalog,
        profile=_profile(),
        item_qalys={"short": 0.05, "long": 0.04},
    )
    new_penalty, details = expected_stack_interaction_qaly(
        item_ids=["short", "long"],
        catalog_entries=catalog,
        profile=_profile(),
        item_qalys={"short": 0.05, "long": 0.04},
        item_active_years={"short": 1.0, "long": 10.0},
    )

    assert old_penalty == pytest.approx(-0.018)
    assert abs(new_penalty) < abs(old_penalty) * 0.25
    assert details[0]["time_aware"] is True


class TestMechanismClusters:
    """Exercise the mechanism-cluster diminishing-returns schedules."""

    def test_nad_precursor_cluster_has_steep_retention(self):
        """NR and NMN should not stack — shared NAD+ salvage pathway."""
        from optiqal.stack_interactions import BENEFIT_OVERLAP_RETENTION
        schedule = BENEFIT_OVERLAP_RETENTION["nad_precursor"]
        # First item full benefit, second item retains <= 30% (shared pathway).
        assert schedule[0] == 1.0
        assert schedule[1] <= 0.30

    def test_anti_inflammatory_cluster_exists(self):
        from optiqal.stack_interactions import BENEFIT_OVERLAP_RETENTION
        # Must have an anti-inflammatory cluster so polyphenols don't stack.
        assert "anti_inflammatory" in BENEFIT_OVERLAP_RETENTION
        schedule = BENEFIT_OVERLAP_RETENTION["anti_inflammatory"]
        assert schedule[1] <= 0.50

    def test_polyphenol_stacking_penalized(self):
        """Three polyphenols should produce a nonzero overlap penalty."""
        catalog = {
            "a": CatalogEntry(
                id="a", name="Curcumin-like", category="supplement_current",
                hr_observed=0.95, log_sd=0.1, conf_alpha=1.0, conf_beta=1.0,
                annual_cost=40, benefit_tags=["anti_inflammatory"],
            ),
            "b": CatalogEntry(
                id="b", name="Quercetin-like", category="supplement_current",
                hr_observed=0.95, log_sd=0.1, conf_alpha=1.0, conf_beta=1.0,
                annual_cost=60, benefit_tags=["anti_inflammatory"],
            ),
            "c": CatalogEntry(
                id="c", name="Apigenin-like", category="supplement_current",
                hr_observed=0.95, log_sd=0.1, conf_alpha=1.0, conf_beta=1.0,
                annual_cost=76, benefit_tags=["anti_inflammatory"],
            ),
        }
        penalty, details = expected_stack_interaction_qaly(
            item_ids=list(catalog),
            catalog_entries=catalog,
            profile=_profile(),
            item_qalys={"a": 0.05, "b": 0.04, "c": 0.03},
        )
        assert penalty < 0
        # Expected tagged cluster is the dominant overlap source.
        cluster_details = [d for d in details if d["id"] == "benefit_overlap:anti_inflammatory"]
        assert len(cluster_details) == 1
        assert cluster_details[0]["matched_tag_count"] == 3

    def test_catalog_polyphenols_carry_anti_inflammatory_tag(self):
        """After annotation, curcumin/quercetin/apigenin should share the cluster."""
        for item_id in ("curcumin_250", "quercetin_500", "apigenin_50"):
            entry = CATALOG.get(item_id)
            assert entry is not None, item_id
            assert "anti_inflammatory" in entry.benefit_tags, item_id

    def test_catalog_nad_precursors_tagged(self):
        for item_id in ("nr_300", "nmn_500"):
            entry = CATALOG.get(item_id)
            assert entry is not None, item_id
            assert "nad_precursor" in entry.benefit_tags, item_id
