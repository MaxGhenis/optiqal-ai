"""Synthetic quantity fixtures; no personal records or health-effect estimates."""

import json
from decimal import Decimal, localcontext

import pytest

from optiqal.product_composition import (
    IngredientAmount,
    ProductChange,
    ProductComposition,
    ProductUse,
    remove_products,
    replace_product,
)


def synthetic_product(product_id, *ingredients, complete=True, servings=1):
    return ProductUse(
        ProductComposition(
            product_id,
            tuple(IngredientAmount(*ingredient) for ingredient in ingredients),
            composition_complete=complete,
            source="synthetic test fixture; no commercial product or personal data",
        ),
        servings_per_day=servings,
    )


@pytest.fixture
def shared_inventory():
    return (
        synthetic_product("synthetic_single", ("ingredient_a", "5", "g")),
        synthetic_product(
            "synthetic_mix",
            ("ingredient_a", "2500", "mg"),
            ("ingredient_b", "100", "mg"),
        ),
    )


def ingredient(change, ingredient_id="ingredient_a"):
    return next(
        row
        for row in change.to_payload()["ingredients"]
        if row["ingredient_id"] == ingredient_id
    )


def test_removing_one_shared_product_is_a_partial_reduction(shared_inventory):
    change = remove_products(shared_inventory, ("synthetic_single",))
    row = ingredient(change)
    assert row["before"]["total_per_day"] == {"amount": "7500", "unit": "mg"}
    assert row["after"]["total_per_day"] == {"amount": "2500", "unit": "mg"}
    assert row["delta_per_day"] == {"amount": "-5000", "unit": "mg"}
    assert row["change"] == "reduced"
    assert row["full_withdrawal"] is False
    assert row["unsupported_reasons"] == ["dose_response_not_modeled"]
    assert ingredient(change, "ingredient_b")["change"] == "unchanged"
    assert change.to_payload()["retained_product_ids"] == ["synthetic_mix"]
    assert [c["product_id"] for c in row["before"]["contributions"]] == [
        "synthetic_mix",
        "synthetic_single",
    ]


def test_removing_all_shared_products_withdraws_supplied_exposure(shared_inventory):
    change = remove_products(shared_inventory, ("synthetic_single", "synthetic_mix"))
    row = ingredient(change)
    assert row["after"]["total_per_day"] == {"amount": "0", "unit": "mg"}
    assert row["change"] == "withdrawn"
    assert row["full_withdrawal"] is True
    assert row["delta_per_day"] == {"amount": "-7500", "unit": "mg"}
    assert change.to_payload()["scope"] == "supplied_products_per_day"
    # A physical withdrawal does not validate a health-effect contrast.
    assert change.to_payload()["ranking_eligibility"] == {
        "eligible": False,
        "unsupported_reasons": ["product_effect_mapping_unavailable"],
    }


def test_replacement_retains_overlap_and_accounts_for_new_ingredients(shared_inventory):
    replacement = synthetic_product(
        "synthetic_replacement",
        ("ingredient_a", "1", "g"),
        ("ingredient_c", "0.2", "g"),
    )
    change = replace_product(shared_inventory, "synthetic_single", replacement)
    row = ingredient(change)
    assert row["after"]["total_per_day"] == {"amount": "3500", "unit": "mg"}
    assert row["delta_per_day"] == {"amount": "-4000", "unit": "mg"}
    assert row["full_withdrawal"] is False
    assert ingredient(change, "ingredient_c")["change"] == "introduced"
    assert ingredient(change, "ingredient_b")["change"] == "unchanged"
    assert change.to_payload()["added_product_ids"] == ["synthetic_replacement"]


def test_equivalent_replacement_has_no_quantity_change(shared_inventory):
    replacement = synthetic_product(
        "synthetic_equivalent", ("ingredient_a", "5000", "mg")
    )
    row = ingredient(replace_product(shared_inventory, "synthetic_single", replacement))
    assert row["change"] == "unchanged"
    assert row["delta_per_day"] == {"amount": "0", "unit": "mg"}
    assert row["full_withdrawal"] is False


@pytest.mark.parametrize("unit", ["mcg", "ug", "µg", "μg"])
def test_mass_conversion_includes_microgram_spellings(unit):
    before = (
        synthetic_product(
            "synthetic_micro", ("ingredient_a", "250", unit), servings="2"
        ),
    )
    after = (synthetic_product("synthetic_milli", ("ingredient_a", "0.5", "mg")),)
    row = ingredient(ProductChange(before, after))
    assert row["before"]["total_per_day"] == {"amount": "0.5", "unit": "mg"}
    assert row["change"] == "unchanged"


@pytest.mark.parametrize("unit", ["IU", "CFU"])
def test_non_mass_units_are_summed_only_within_their_unit(unit):
    uses = (
        synthetic_product("synthetic_one", ("ingredient_a", 100, unit)),
        synthetic_product("synthetic_two", ("ingredient_a", 50, unit), servings=2),
    )
    row = ingredient(remove_products(uses, ("synthetic_one",)))
    assert row["before"]["total_per_day"] == {"amount": "200", "unit": unit}
    assert row["after"]["total_per_day"] == {"amount": "100", "unit": unit}


@pytest.mark.parametrize("other_unit", ["IU", "CFU"])
def test_incompatible_units_remain_separate(other_unit):
    uses = (
        synthetic_product("synthetic_mass", ("ingredient_a", 1, "mg")),
        synthetic_product("synthetic_other", ("ingredient_a", 2, other_unit)),
    )
    row = ingredient(remove_products(uses, ("synthetic_mass",)))
    assert row["before"]["known_totals_per_day"] == [
        {"amount": "2", "unit": other_unit},
        {"amount": "1", "unit": "mg"},
    ]
    assert row["before"]["total_per_day"] is None
    assert row["after"]["total_per_day"] is None
    assert row["delta_per_day"] is None
    assert row["change"] == "unknown"
    assert row["full_withdrawal"] is False
    assert "incompatible_ingredient_units" in row["unsupported_reasons"]


def test_incompatible_units_across_replacement_are_not_subtracted():
    before = (synthetic_product("synthetic_mass", ("ingredient_a", 1, "mg")),)
    after = (synthetic_product("synthetic_activity", ("ingredient_a", 2, "IU")),)
    row = ingredient(ProductChange(before, after))
    assert row["delta_per_day"] is None
    assert row["change"] == "unknown"


def test_unknown_amount_is_retained_beside_known_subtotal():
    uses = (
        synthetic_product("synthetic_known", ("ingredient_a", 5, "g")),
        synthetic_product("synthetic_unknown", ("ingredient_a", None, "mg")),
    )
    row = ingredient(remove_products(uses, ("synthetic_known",)))
    assert row["before"]["known_totals_per_day"] == [{"amount": "5000", "unit": "mg"}]
    assert row["before"]["total_per_day"] is None
    assert row["after"]["known_totals_per_day"] == []
    assert row["after"]["total_per_day"] is None
    assert row["after"]["contributions"][0]["amount_per_serving"] is None
    assert row["after"]["contributions"][0]["unknown_reasons"] == [
        "unknown_ingredient_amount"
    ]
    assert row["delta_per_day"] is None
    assert row["full_withdrawal"] is False


@pytest.mark.parametrize(
    "unit,reason",
    [
        (None, "unknown_ingredient_unit"),
        ("scoop", "unsupported_ingredient_unit"),
        ("MG", "unsupported_ingredient_unit"),
    ],
)
def test_unknown_units_preserve_original_amount_and_label(unit, reason):
    use = synthetic_product("synthetic_unknown", ("ingredient_a", "2.5", unit))
    row = ingredient(remove_products((use,), (use.product.product_id,)))
    contribution = row["before"]["contributions"][0]
    assert contribution["amount_per_serving"] == "2.5"
    assert contribution["unit"] == unit
    assert contribution["quantity_per_day"] is None
    assert contribution["unknown_reasons"] == [reason]
    assert row["change"] == "unknown"
    assert row["full_withdrawal"] is False


def test_unknown_servings_do_not_assume_one_serving():
    use = synthetic_product(
        "synthetic_unknown", ("ingredient_a", 5, "g"), servings=None
    )
    row = ingredient(remove_products((use,), (use.product.product_id,)))
    assert row["before"]["total_per_day"] is None
    assert row["before"]["contributions"][0]["servings_per_day"] is None
    assert "unknown_servings_per_day" in row["unsupported_reasons"]
    assert row["full_withdrawal"] is False


def test_incomplete_other_product_prevents_claiming_absence():
    known = synthetic_product("synthetic_known", ("ingredient_a", 5, "g"))
    incomplete = ProductUse(ProductComposition("synthetic_unlisted", ()))
    row = ingredient(remove_products((known, incomplete), (known.product.product_id,)))
    assert row["before"]["known_totals_per_day"] == [{"amount": "5000", "unit": "mg"}]
    assert row["after"]["total_per_day"] is None
    assert row["after"]["incomplete_product_ids"] == ["synthetic_unlisted"]
    assert row["full_withdrawal"] is False
    assert row["change"] == "unknown"


def test_entirely_unknown_composition_has_explicit_inventory_reason():
    use = ProductUse(ProductComposition("synthetic_unlisted", ()))
    payload = remove_products((use,), (use.product.product_id,)).to_payload()
    assert payload["ingredients"] == []
    assert payload["before_products"][0]["composition_complete"] is False
    assert (
        "incomplete_composition"
        in payload["ranking_eligibility"]["unsupported_reasons"]
    )


def test_explicit_zero_servings_do_not_add_uncertainty():
    known = synthetic_product("synthetic_known", ("ingredient_a", 5, "g"))
    unused = synthetic_product(
        "synthetic_unused", ("ingredient_a", None, None), complete=False, servings=0
    )
    row = ingredient(remove_products((known, unused), (known.product.product_id,)))
    assert row["change"] == "withdrawn"
    assert row["after"]["unknown_reasons"] == []


def test_changed_servings_are_scaled_once(shared_inventory):
    single, mix = shared_inventory
    row = ingredient(
        ProductChange(shared_inventory, (ProductUse(single.product, "0.5"), mix))
    )
    assert row["after"]["total_per_day"] == {"amount": "5000", "unit": "mg"}
    assert row["delta_per_day"] == {"amount": "-2500", "unit": "mg"}
    assert len(row["after"]["contributions"]) == 2


def test_accounting_is_order_invariant(shared_inventory):
    forward = remove_products(shared_inventory, ("synthetic_single",)).to_payload()
    reverse = remove_products(
        reversed(shared_inventory), ("synthetic_single",)
    ).to_payload()
    assert forward == reverse


def test_exact_decimal_accounting_preserves_tiny_retained_amounts():
    uses = (
        synthetic_product("synthetic_large", ("ingredient_a", "1", "mg")),
        synthetic_product("synthetic_tiny", ("ingredient_a", "1e-40", "mg")),
    )
    with localcontext() as context:
        context.prec = 6
        context.Emin = -3
        context.Emax = 3
        row = ingredient(remove_products(uses, ("synthetic_large",)))
    assert Decimal(row["before"]["total_per_day"]["amount"]) == Decimal(
        "1.0000000000000000000000000000000000000001"
    )
    assert Decimal(row["after"]["total_per_day"]["amount"]) == Decimal("1e-40")
    assert row["delta_per_day"] == {"amount": "-1", "unit": "mg"}
    assert row["change"] == "reduced"
    assert row["full_withdrawal"] is False


def test_fractional_servings_preserve_exact_decimal_values():
    use = synthetic_product(
        "synthetic_fraction", ("ingredient_a", "0.1", "mg"), servings="0.2"
    )
    row = ingredient(remove_products((use,), (use.product.product_id,)))
    assert row["before"]["total_per_day"] == {"amount": "0.02", "unit": "mg"}


def test_duplicate_products_are_rejected_instead_of_double_counted(shared_inventory):
    single, mix = shared_inventory
    with pytest.raises(ValueError, match="Duplicate product IDs"):
        ProductChange((single, single, mix), ())
    with pytest.raises(ValueError, match="Duplicate product IDs"):
        ProductChange((), (single, single))


def test_duplicate_ingredient_rows_are_rejected():
    with pytest.raises(ValueError, match="Duplicate ingredient IDs"):
        synthetic_product(
            "synthetic_ambiguous",
            ("ingredient_a", 5, "g"),
            ("ingredient_a", 5000, "mg"),
        )


def test_replacement_cannot_duplicate_a_retained_product(shared_inventory):
    with pytest.raises(ValueError, match="Duplicate product IDs"):
        replace_product(shared_inventory, "synthetic_single", shared_inventory[1])


def test_changed_composition_requires_versioned_product_identity(shared_inventory):
    replacement = synthetic_product("synthetic_single", ("ingredient_a", 1, "g"))
    with pytest.raises(ValueError, match="new product/version ID"):
        replace_product(shared_inventory, "synthetic_single", replacement)


@pytest.mark.parametrize(
    "removed", [("missing",), ("synthetic_single", "synthetic_single")]
)
def test_invalid_removals_are_rejected(shared_inventory, removed):
    with pytest.raises(ValueError):
        remove_products(shared_inventory, removed)


@pytest.mark.parametrize(
    "value",
    [-1, "-0.01", float("inf"), float("nan"), "NaN", "Infinity", "5 g", True, object()],
)
def test_invalid_amounts_and_servings_are_rejected(value):
    with pytest.raises(ValueError):
        IngredientAmount("ingredient_a", value, "mg")
    with pytest.raises(ValueError):
        synthetic_product(
            "synthetic_invalid", ("ingredient_a", 1, "mg"), servings=value
        )


@pytest.mark.parametrize(
    "identifier", ["", "Ingredient_a", " ingredient_a", "ingredient a"]
)
def test_noncanonical_identifiers_are_rejected(identifier):
    with pytest.raises(ValueError, match="canonical"):
        IngredientAmount(identifier, 1, "mg")
    with pytest.raises(ValueError, match="canonical"):
        ProductComposition(identifier, ())


def test_completeness_requires_a_boolean():
    with pytest.raises(ValueError, match="boolean"):
        ProductComposition("synthetic_invalid", (), composition_complete="false")


def test_payload_is_json_safe_and_contains_no_effect_or_recommendation_fields(
    shared_inventory,
):
    payload = remove_products(shared_inventory, ("synthetic_single",)).to_payload()
    assert json.loads(json.dumps(payload, allow_nan=False)) == payload

    def keys(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield key
                yield from keys(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys(child)

    assert not {
        "qaly",
        "total_qaly",
        "net_value",
        "verdict",
        "recommendation",
        "hazard_ratio",
    } & set(keys(payload))


def test_empty_inventory_is_a_valid_noop():
    payload = ProductChange((), ()).to_payload()
    assert payload["ingredients"] == []
    assert payload["removed_product_ids"] == []
    assert payload["ranking_eligibility"]["eligible"] is False
