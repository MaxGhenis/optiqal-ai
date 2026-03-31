"""Tests for stack-level interaction penalties."""

import pytest

from optiqal.catalog import CatalogEntry

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
