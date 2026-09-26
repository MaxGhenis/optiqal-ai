"""Tests for insurance-aware costing.

Every ``annual_cost`` in the catalog is a cash retail price. That is correct
for supplements, which no payer covers, and wrong for prescriptions and DME.
Pricing both at retail systematically favours cash-pay supplements over
clinical interventions in the $/QALY ranking, because only the supplements
were ever priced right. These tests pin the conversion from sticker price to
expected out-of-pocket cost.
"""

from __future__ import annotations

import pytest

from optiqal.catalog import (
    COVERABLE_TIERS,
    DC_MEDICAID_MANAGED_CARE,
    UNINSURED,
    AccessProfile,
    InsuranceContext,
    get_catalog,
    simulate_catalog,
)
from optiqal.profile import Profile


def _profile() -> Profile:
    return Profile(
        age=39,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="active",
    )


# --- the conversion itself -------------------------------------------------


def test_no_insurance_context_leaves_every_price_at_retail():
    """Omitting insurance must reproduce the pre-insurance behaviour exactly."""
    for entry in get_catalog().values():
        assert entry.effective_annual_cost(None) == pytest.approx(
            float(entry.annual_cost) + float(entry.bundle_cost_share)
        )


def test_uninsured_context_matches_no_context():
    """UNINSURED is the explicit spelling of "price everything at retail"."""
    for entry in get_catalog().values():
        assert entry.effective_annual_cost(UNINSURED) == pytest.approx(
            entry.effective_annual_cost(None)
        )


@pytest.mark.parametrize("tier", sorted(COVERABLE_TIERS))
def test_medicaid_reduces_cost_for_coverable_tiers(tier):
    """A payer with no cost sharing must reduce, not raise, a covered price."""
    access = AccessProfile(tier=tier, coverage_outlook="likely")
    retail = 1000.0
    out_of_pocket = DC_MEDICAID_MANAGED_CARE.patient_cost(retail, access)
    assert 0 < out_of_pocket < retail


@pytest.mark.parametrize("tier", ["behavioral", "otc", "cash_pay"])
def test_uncoverable_tiers_always_cost_sticker(tier):
    """Supplements are OTC. No payer covers them, so insurance changes nothing."""
    access = AccessProfile(tier=tier, coverage_outlook="likely")
    assert DC_MEDICAID_MANAGED_CARE.patient_cost(500.0, access) == 500.0


def test_coverage_outlook_orders_expected_cost():
    """Better coverage outlook must never cost more than a worse one."""
    costs = [
        DC_MEDICAID_MANAGED_CARE.patient_cost(
            1000.0, AccessProfile(tier="dme_rx", coverage_outlook=outlook)
        )
        for outlook in ("likely", "mixed", "unlikely", "na")
    ]
    assert costs == sorted(costs), costs


def test_na_outlook_falls_back_to_full_retail():
    """An unclassified item must not get a silent discount."""
    access = AccessProfile(tier="dme_rx", coverage_outlook="na")
    assert DC_MEDICAID_MANAGED_CARE.patient_cost(800.0, access) == 800.0


def test_zero_and_free_items_stay_free():
    access = AccessProfile(tier="dme_rx", coverage_outlook="likely")
    assert DC_MEDICAID_MANAGED_CARE.patient_cost(0.0, access) == 0.0


def test_denial_probabilities_are_clamped():
    """A malformed prior must not produce a negative or inflated cost."""
    wild = InsuranceContext(
        name="wild",
        cost_share=0.0,
        denial_rate={"likely": -5.0, "mixed": 42.0},
    )
    lo = wild.patient_cost(100.0, AccessProfile("dme_rx", "likely"))
    hi = wild.patient_cost(100.0, AccessProfile("dme_rx", "mixed"))
    assert lo == pytest.approx(0.0)
    assert hi == pytest.approx(100.0)


# --- effect on the ranking -------------------------------------------------


def test_apap_gets_cheaper_under_medicaid_and_supplements_do_not():
    """The whole point: covered DME repriced, cash-pay supplements untouched."""
    catalog = get_catalog()
    apap = catalog["apap_nightly"]
    mix_active = catalog["caakg_2000"]

    assert apap.effective_annual_cost(DC_MEDICAID_MANAGED_CARE) < (
        apap.effective_annual_cost(UNINSURED)
    )
    assert mix_active.effective_annual_cost(DC_MEDICAID_MANAGED_CARE) == pytest.approx(
        mix_active.effective_annual_cost(UNINSURED)
    )


def test_simulate_catalog_threads_insurance_through_to_cost():
    """simulate_catalog must actually use the insurance context it is given."""
    profile = _profile()
    retail = {r["id"]: r for r in simulate_catalog(profile, n_simulations=2_000)}
    covered = {
        r["id"]: r
        for r in simulate_catalog(
            profile, n_simulations=2_000, insurance=DC_MEDICAID_MANAGED_CARE
        )
    }
    assert (
        covered["apap_nightly"]["annual_cost"] < retail["apap_nightly"]["annual_cost"]
    )
    assert (
        covered["apap_nightly"]["effective_annual_cost"]
        < (retail["apap_nightly"]["effective_annual_cost"])
    )
    # The sticker price is still reported, so the discount stays auditable.
    assert (
        covered["apap_nightly"]["retail_annual_cost"]
        == (retail["apap_nightly"]["retail_annual_cost"])
    )
    # QALYs are a clinical quantity and must not move when only price changes.
    assert covered["apap_nightly"]["days"] == pytest.approx(
        retail["apap_nightly"]["days"]
    )


def test_supplement_prices_are_untouched_end_to_end():
    """A cash-pay supplement must cost the same under any insurance context."""
    profile = _profile()
    retail = {r["id"]: r for r in simulate_catalog(profile, n_simulations=2_000)}
    covered = {
        r["id"]: r
        for r in simulate_catalog(
            profile, n_simulations=2_000, insurance=DC_MEDICAID_MANAGED_CARE
        )
    }
    for item_id in ("caakg_2000", "glucosamine_sulfate_750", "l_theanine_200"):
        assert covered[item_id]["annual_cost"] == pytest.approx(
            retail[item_id]["annual_cost"]
        ), item_id


def test_qalys_are_invariant_to_insurance_across_the_catalog():
    profile = _profile()
    retail = {r["id"]: r for r in simulate_catalog(profile, n_simulations=2_000)}
    covered = {
        r["id"]: r
        for r in simulate_catalog(
            profile, n_simulations=2_000, insurance=DC_MEDICAID_MANAGED_CARE
        )
    }
    for item_id, row in retail.items():
        assert covered[item_id]["days"] == pytest.approx(row["days"]), item_id
