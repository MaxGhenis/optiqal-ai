"""Tests for the Blueprint Longevity Mix bundle and its ingredients.

The Blueprint Longevity Mix is a multi-ingredient longevity supplement that
Max takes (1 scoop/day, 14.8 g, ~$537/yr, 30 servings/package). It contains
11 actives. This module verifies that all 11 are represented in the catalog,
that they are wired into the ``blueprint_longevity_mix`` bundle with cost
shares that sum to the real retail price, and that each newly-added ingredient
carries cited evidence and a recognized study-quality tier.

Per-ingredient ground-truth doses (1 scoop = 14.8 g):
  CaAKG 2000 mg, Taurine 1500 mg, Creatine monohydrate 2500 mg,
  Glycine 1200 mg, L-Lysine 1000 mg, Glucosamine sulfate 750 mg,
  Reduced glutathione 250 mg, Sodium hyaluronate 120 mg, L-Theanine 200 mg,
  Magnesium citrate 150 mg, Vitamin C 250 mg.
"""

from __future__ import annotations

import pytest

from optiqal.catalog import (
    BUNDLE_ALLOCATIONS,
    get_catalog,
    simulate_catalog,
)
from optiqal.confounding import STUDY_QUALITY_SHRINKAGE
from optiqal.profile import Profile

BLUEPRINT_BUNDLE_ID = "blueprint_longevity_mix"


def get_entry(item_id):
    """Resolve a catalog entry by id (None if absent)."""
    return get_catalog().get(item_id)


def _canonical_profile() -> Profile:
    """A healthy reference profile for simulate_catalog smoke tests."""
    return Profile(
        age=39,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="light",
    )


def _results_by_id(results) -> dict:
    """Index simulate_catalog's list-of-dicts output by item id."""
    return {row["id"]: row for row in results}


# The 11 actives in the Blueprint Longevity Mix, mapped to catalog ids.
# 5 ids are newly added; 6 reuse pre-existing catalog entries.
MIX_INGREDIENT_IDS = (
    # Newly added entries (cited priors required)
    "caakg_2000",
    "glucosamine_sulfate_750",
    "l_lysine_1000",
    "glutathione_250",
    "l_theanine_200",
    # Reused pre-existing entries
    "creatine_5g",
    "taurine_500_topup",
    "glycine_2g",
    "hyaluronic_acid_120",
    "vitamin_c_500_extra",
    "magnesium_citrate_150",
)

# The 5 ingredients that this task introduces as new catalog entries.
NEW_MIX_INGREDIENT_IDS = (
    "caakg_2000",
    "glucosamine_sulfate_750",
    "l_lysine_1000",
    "glutathione_250",
    "l_theanine_200",
)

# Real retail price of the Mix: ~$537/yr.
MIX_ANNUAL_PRICE = 537.0


def test_all_eleven_ingredients_exist_in_catalog():
    """Every one of the 11 Mix actives resolves to a catalog entry."""
    catalog = get_catalog()
    missing = [i for i in MIX_INGREDIENT_IDS if i not in catalog]
    assert not missing, f"Mix ingredients missing from catalog: {missing}"
    assert len(MIX_INGREDIENT_IDS) == 11


def test_all_ingredients_tagged_with_blueprint_bundle_id():
    """All 11 Mix actives carry bundle_id == 'blueprint_longevity_mix'."""
    for ingredient_id in MIX_INGREDIENT_IDS:
        entry = get_entry(ingredient_id)
        assert entry is not None, f"{ingredient_id} not in catalog"
        assert entry.bundle_id == BLUEPRINT_BUNDLE_ID, (
            f"{ingredient_id} bundle_id is {entry.bundle_id!r}, "
            f"expected {BLUEPRINT_BUNDLE_ID!r}"
        )


def test_all_ingredients_in_bundle_allocations():
    """All 11 Mix actives appear in BUNDLE_ALLOCATIONS under the Mix."""
    for ingredient_id in MIX_INGREDIENT_IDS:
        assert ingredient_id in BUNDLE_ALLOCATIONS, (
            f"{ingredient_id} not in BUNDLE_ALLOCATIONS"
        )
        bundle_id, _share = BUNDLE_ALLOCATIONS[ingredient_id]
        assert bundle_id == BLUEPRINT_BUNDLE_ID, (
            f"{ingredient_id} allocated to {bundle_id!r}, "
            f"expected {BLUEPRINT_BUNDLE_ID!r}"
        )


def test_bundle_cost_shares_sum_to_retail_price():
    """The Mix ingredients' bundle_cost_share sums to ~$537/yr."""
    catalog = get_catalog()
    total = sum(
        catalog[i].bundle_cost_share for i in MIX_INGREDIENT_IDS if i in catalog
    )
    assert total == pytest.approx(MIX_ANNUAL_PRICE, abs=5.0), (
        f"Mix bundle cost-share total is {total}, expected ~{MIX_ANNUAL_PRICE}"
    )


def test_bundle_membership_count():
    """Exactly the 11 Mix actives belong to the Blueprint bundle."""
    catalog = get_catalog()
    members = {eid for eid, e in catalog.items() if e.bundle_id == BLUEPRINT_BUNDLE_ID}
    assert members == set(MIX_INGREDIENT_IDS), (
        f"Blueprint bundle members {members} != expected {set(MIX_INGREDIENT_IDS)}"
    )


def test_hyaluronic_acid_remains_a_bundle_member():
    """The pre-existing hyaluronic_acid_120 membership is preserved."""
    entry = get_entry("hyaluronic_acid_120")
    assert entry is not None
    assert entry.bundle_id == BLUEPRINT_BUNDLE_ID


def test_new_entries_have_nonempty_sources():
    """Each newly added ingredient cites at least one http(s) source."""
    for ingredient_id in NEW_MIX_INGREDIENT_IDS:
        entry = get_entry(ingredient_id)
        assert entry is not None, f"{ingredient_id} not in catalog"
        assert entry.sources, f"{ingredient_id} has no sources"
        assert all(s.startswith("http") for s in entry.sources), (
            f"{ingredient_id} has a malformed source URL: {entry.sources}"
        )


def test_new_entries_have_valid_study_quality_tier():
    """Each newly added ingredient uses a recognized study_quality tier."""
    for ingredient_id in NEW_MIX_INGREDIENT_IDS:
        entry = get_entry(ingredient_id)
        assert entry is not None, f"{ingredient_id} not in catalog"
        assert entry.study_quality in STUDY_QUALITY_SHRINKAGE, (
            f"{ingredient_id} study_quality {entry.study_quality!r} "
            "is not a recognized tier"
        )


def test_new_entries_have_nonempty_notes():
    """Each newly added ingredient documents its prior in notes."""
    for ingredient_id in NEW_MIX_INGREDIENT_IDS:
        entry = get_entry(ingredient_id)
        assert entry is not None
        assert entry.notes.strip(), f"{ingredient_id} has empty notes"


def test_new_entries_hr_in_reasonable_range():
    """Newly added HRs stay within the catalog's sanity bounds."""
    for ingredient_id in NEW_MIX_INGREDIENT_IDS:
        entry = get_entry(ingredient_id)
        assert entry is not None
        assert 0.5 <= entry.hr_observed <= 1.5, (
            f"{ingredient_id} HR {entry.hr_observed} out of range"
        )


def test_glucosamine_uses_observational_tier_and_cites_uk_biobank():
    """Glucosamine has confounded prospective-cohort mortality data.

    The raw UK Biobank all-cause mortality HR is 0.85 (95% CI 0.82-0.89), but
    that is selection-bias inflated; the catalog enters a conservative sub-null
    HR and an observational tier so the confounding machinery shrinks it.
    """
    entry = get_entry("glucosamine_sulfate_750")
    assert entry is not None
    # Conservative sub-null HR, not the raw 0.85 and not a fabricated effect.
    assert 0.85 < entry.hr_observed < 1.0, (
        f"glucosamine HR {entry.hr_observed} should be a conservative sub-null "
        "value above the confounded raw 0.85"
    )
    # Tier must reflect confounded observational evidence (heavy shrinkage),
    # and must be one of the tiers actually defined in confounding.py.
    assert entry.study_quality in STUDY_QUALITY_SHRINKAGE
    assert entry.study_quality in (
        "observational_speculative",
        "cohort_large",
        "cohort_small",
    ), f"glucosamine tier {entry.study_quality} should reflect cohort data"
    # Cites the UK Biobank all-cause mortality study (Li et al., PMID 32253185).
    assert any("32253185" in s for s in entry.sources), (
        "glucosamine should cite the UK Biobank mortality study (PMID 32253185)"
    )


def test_caakg_is_animal_mechanism_tier_near_null():
    """CaAKG mortality evidence is animal-only -> near-null, mechanism tier."""
    entry = get_entry("caakg_2000")
    assert entry is not None
    # Real confounding.py tier for animal/mechanistic evidence.
    assert entry.study_quality == "animal_or_mechanistic", (
        f"CaAKG tier {entry.study_quality} should be animal_or_mechanistic "
        "(human lifespan data absent)"
    )
    # No fabricated human mortality benefit: HR at/near null.
    assert entry.hr_observed == pytest.approx(1.0, abs=0.001), (
        f"CaAKG HR {entry.hr_observed} should be null (no human mortality data)"
    )


def test_simulate_catalog_returns_mix_items_with_ci():
    """simulate_catalog still runs and returns Mix items with net_qaly_ci."""
    results = simulate_catalog(_canonical_profile(), n_simulations=600, random_state=7)
    assert isinstance(results, list) and results
    by_id = _results_by_id(results)
    for ingredient_id in MIX_INGREDIENT_IDS:
        assert ingredient_id in by_id, (
            f"{ingredient_id} missing from simulate_catalog output"
        )
        res = by_id[ingredient_id]
        assert "net_qaly_ci" in res, f"{ingredient_id} missing net_qaly_ci"
        lo, hi = res["net_qaly_ci"]
        assert lo <= hi, f"{ingredient_id} CI bounds inverted: {lo} > {hi}"
        # Effective cost should include the bundle share.
        assert res["effective_annual_cost"] >= 0.0


def test_entry_effective_annual_cost_equals_annual_plus_bundle_share():
    """CatalogEntry.effective_annual_cost() = annual_cost + bundle_cost_share."""
    entry = get_entry("caakg_2000")
    assert entry is not None
    assert entry.annual_cost == 0.0  # CaAKG has no separate standalone cost
    assert entry.bundle_cost_share == pytest.approx(108.0, abs=1.0)
    assert entry.effective_annual_cost() == pytest.approx(
        entry.annual_cost + entry.bundle_cost_share
    )


def test_simulate_catalog_bundle_cost_scales_with_share():
    """Lifetime cost in the sim scales with the per-item bundle share.

    The sim reports a survival-weighted, discounted *lifetime* cost under the
    ``effective_annual_cost`` key (annual effective cost x discounted
    cost-years). For two near-null-mortality bundled items that share the same
    discounted cost-year factor, the ratio of their reported costs should equal
    the ratio of their bundle shares.
    """
    results = simulate_catalog(_canonical_profile(), n_simulations=400, random_state=11)
    by_id = _results_by_id(results)
    caakg = get_entry("caakg_2000")
    lysine = get_entry("l_lysine_1000")
    assert caakg is not None and lysine is not None

    caakg_cost = by_id["caakg_2000"]["effective_annual_cost"]
    lysine_cost = by_id["l_lysine_1000"]["effective_annual_cost"]
    assert caakg_cost > 0.0
    assert lysine_cost > 0.0
    # Both are null-HR, no-direct-mortality items -> identical cost-year factor,
    # so the lifetime-cost ratio equals the bundle-share ratio.
    assert caakg_cost / lysine_cost == pytest.approx(
        caakg.bundle_cost_share / lysine.bundle_cost_share, rel=1e-3
    )
