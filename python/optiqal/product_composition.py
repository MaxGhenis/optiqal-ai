"""Deterministic product quantities, independent of health-effect estimates.

Amounts describe one labeled serving; exposure describes the supplied products
per day. Ingredient IDs must already identify the same substance and quantity
basis (for example, elemental magnesium, not magnesium-salt mass). No ingredient
aliases, potency conversions, dietary exposure, or dose responses are inferred.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Iterable

# Only dimension-preserving conversions. IU and CFU cannot be converted to mass.
_UNITS = {
    "g": ("mg", Decimal("1000")),
    "mg": ("mg", Decimal("1")),
    "mcg": ("mg", Decimal("0.001")),
    "ug": ("mg", Decimal("0.001")),
    "µg": ("mg", Decimal("0.001")),
    "μg": ("mg", Decimal("0.001")),
    "IU": ("IU", Decimal("1")),
    "CFU": ("CFU", Decimal("1")),
}
AmountInput = Decimal | str | int | float


def _identifier(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]*", value):
        raise ValueError("IDs must be nonempty, canonical lowercase identifiers")


def _amount(value: AmountInput | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int, float)):
        raise ValueError("Amounts must be nonnegative finite numbers or None")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Amounts must be nonnegative finite numbers or None") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Amounts must be nonnegative finite numbers or None")
    return number


def _decimal(value: Fraction) -> Decimal:
    """Exact finite-decimal arithmetic, independent of the caller's context.

    All inputs and conversion factors are finite decimals, so denominators have
    only factors 2 and 5. Constructing a decimal string avoids rounding and
    underflow, including when the caller has narrowed their Decimal context.
    """
    denominator = value.denominator
    twos = fives = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    assert denominator == 1  # Only finite-decimal inputs enter this module.
    places = max(twos, fives)
    coefficient = value.numerator * 2 ** (places - twos) * 5 ** (places - fives)
    return Decimal(f"{coefficient}e-{places}")


@dataclass(frozen=True)
class IngredientAmount:
    ingredient_id: str
    amount: AmountInput | None
    unit: str | None

    def __post_init__(self) -> None:
        _identifier(self.ingredient_id)
        object.__setattr__(self, "amount", _amount(self.amount))
        if self.unit is not None and (
            not isinstance(self.unit, str) or not self.unit.strip()
        ):
            raise ValueError("Use None for an unknown unit")


@dataclass(frozen=True)
class ProductComposition:
    product_id: str
    ingredients: tuple[IngredientAmount, ...]
    # Missing metadata must not imply that unlisted ingredients are absent.
    composition_complete: bool = False
    source: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.product_id)
        object.__setattr__(self, "ingredients", tuple(self.ingredients))
        if not all(isinstance(row, IngredientAmount) for row in self.ingredients):
            raise ValueError("Ingredients must be IngredientAmount records")
        ids = [row.ingredient_id for row in self.ingredients]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate ingredient IDs within a product are ambiguous")
        if not isinstance(self.composition_complete, bool):
            raise ValueError("composition_complete must be a boolean")
        if self.source is not None and not isinstance(self.source, str):
            raise ValueError("source must be text or None")


@dataclass(frozen=True)
class ProductUse:
    product: ProductComposition
    servings_per_day: AmountInput | None = 1

    def __post_init__(self) -> None:
        if not isinstance(self.product, ProductComposition):
            raise ValueError("product must be a ProductComposition")
        object.__setattr__(self, "servings_per_day", _amount(self.servings_per_day))


def _inventory(uses: Iterable[ProductUse]) -> tuple[ProductUse, ...]:
    result = tuple(uses)
    if not all(isinstance(use, ProductUse) for use in result):
        raise ValueError("Inventory must contain ProductUse records")
    ids = [use.product.product_id for use in result]
    if len(ids) != len(set(ids)):
        raise ValueError(
            "Duplicate product IDs: combine servings instead of counting twice"
        )
    return tuple(sorted(result, key=lambda use: use.product.product_id))


@dataclass(frozen=True)
class ProductChange:
    """Complete before/after supplied inventories, not lists of changed ingredients."""

    before: tuple[ProductUse, ...]
    after: tuple[ProductUse, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "before", _inventory(self.before))
        object.__setattr__(self, "after", _inventory(self.after))
        before = {use.product.product_id: use.product for use in self.before}
        for use in self.after:
            old = before.get(use.product.product_id)
            if old is not None and old != use.product:
                raise ValueError(
                    "Changed composition requires a new product/version ID"
                )

    def to_payload(self) -> dict:
        return compare_product_exposure(self)


def remove_products(
    inventory: Iterable[ProductUse], product_ids: Iterable[str]
) -> ProductChange:
    before = _inventory(inventory)
    removed = tuple(product_ids)
    if len(removed) != len(set(removed)):
        raise ValueError("Duplicate removal IDs")
    if set(removed) - {use.product.product_id for use in before}:
        raise ValueError("Cannot remove a product absent from the supplied inventory")
    return ProductChange(
        before, tuple(use for use in before if use.product.product_id not in removed)
    )


def replace_product(
    inventory: Iterable[ProductUse], product_id: str, replacement: ProductUse
) -> ProductChange:
    removal = remove_products(inventory, (product_id,))
    return ProductChange(removal.before, (*removal.after, replacement))


def _quantity(amount: Decimal, unit: str) -> dict:
    return {"amount": str(amount), "unit": unit}


def _product_payload(use: ProductUse) -> dict:
    return {
        "product_id": use.product.product_id,
        "servings_per_day": (
            str(use.servings_per_day) if use.servings_per_day is not None else None
        ),
        "composition_complete": use.product.composition_complete,
        "source": use.product.source,
        "ingredients": [
            {
                "ingredient_id": row.ingredient_id,
                "amount_per_serving": str(row.amount)
                if row.amount is not None
                else None,
                "unit": row.unit,
            }
            for row in sorted(
                use.product.ingredients, key=lambda row: row.ingredient_id
            )
        ],
    }


def _exposure(
    inventory: tuple[ProductUse, ...], ingredient_id: str, unit: str | None
) -> dict:
    totals: dict[str, Fraction] = {}
    contributions = []
    incomplete_products = []
    reasons = set()
    for use in inventory:
        # An explicitly unused product contributes zero, even if its label is unknown.
        if use.servings_per_day == 0:
            continue
        if not use.product.composition_complete:
            incomplete_products.append(use.product.product_id)
            reasons.add("incomplete_composition")
        for row in use.product.ingredients:
            if row.ingredient_id != ingredient_id:
                continue
            row_reasons = []
            if row.amount is None:
                row_reasons.append("unknown_ingredient_amount")
            if use.servings_per_day is None:
                row_reasons.append("unknown_servings_per_day")
            if row.unit is None:
                row_reasons.append("unknown_ingredient_unit")
            elif row.unit not in _UNITS:
                row_reasons.append("unsupported_ingredient_unit")
            quantity = None
            if not row_reasons:
                assert row.unit is not None
                assert isinstance(row.amount, Decimal)
                assert isinstance(use.servings_per_day, Decimal)
                normalized_unit, factor = _UNITS[row.unit]
                amount = (
                    Fraction(row.amount)
                    * Fraction(use.servings_per_day)
                    * Fraction(factor)
                )
                totals[normalized_unit] = (
                    totals.get(normalized_unit, Fraction(0)) + amount
                )
                quantity = _quantity(_decimal(amount), normalized_unit)
            reasons.update(row_reasons)
            contributions.append(
                {
                    "product_id": use.product.product_id,
                    "amount_per_serving": str(row.amount)
                    if row.amount is not None
                    else None,
                    "unit": row.unit,
                    "servings_per_day": (
                        str(use.servings_per_day)
                        if use.servings_per_day is not None
                        else None
                    ),
                    "quantity_per_day": quantity,
                    "unknown_reasons": row_reasons,
                }
            )
    return {
        "known_totals_per_day": [
            _quantity(_decimal(amount), known_unit)
            for known_unit, amount in sorted(totals.items())
        ],
        # A known subtotal is never silently substituted for the total.
        "total_per_day": (
            _quantity(_decimal(totals.get(unit, Fraction(0))), unit)
            if not reasons and unit is not None
            else None
        ),
        "contributions": contributions,
        "incomplete_product_ids": incomplete_products,
        "unknown_reasons": sorted(reasons),
    }


def compare_product_exposure(change: ProductChange) -> dict:
    """Return an auditable, JSON-safe comparison; never return QALY estimates.

    Decimal quantities serialize as strings. ``full_withdrawal`` means a known
    positive amount becomes a known zero within the supplied products only.
    It does not establish suitability for a catalog's health-effect model.
    """
    active = [
        use for use in (*change.before, *change.after) if use.servings_per_day != 0
    ]
    ingredient_ids = sorted(
        {row.ingredient_id for use in active for row in use.product.ingredients}
    )
    comparisons = []
    all_reasons = {"product_effect_mapping_unavailable"}
    if any(not use.product.composition_complete for use in active):
        all_reasons.add("incomplete_composition")
    for ingredient_id in ingredient_ids:
        units = {
            _UNITS[row.unit][0]
            for use in active
            for row in use.product.ingredients
            if row.ingredient_id == ingredient_id and row.unit in _UNITS
        }
        unit = next(iter(units)) if len(units) == 1 else None
        before = _exposure(change.before, ingredient_id, unit)
        after = _exposure(change.after, ingredient_id, unit)
        reasons = set(before["unknown_reasons"]) | set(after["unknown_reasons"])
        if len(units) > 1:
            reasons.add("incompatible_ingredient_units")
        kind = "unknown"
        delta = None
        if before["total_per_day"] is not None and after["total_per_day"] is not None:
            assert unit is not None
            before_amount = Decimal(before["total_per_day"]["amount"])
            after_amount = Decimal(after["total_per_day"]["amount"])
            delta = _quantity(
                _decimal(Fraction(after_amount) - Fraction(before_amount)), unit
            )
            if before_amount == after_amount:
                kind = "unchanged"
            elif before_amount == 0:
                kind = "introduced"
            elif after_amount == 0:
                kind = "withdrawn"
            elif after_amount < before_amount:
                kind = "reduced"
            else:
                kind = "increased"
        if kind in {"reduced", "increased"}:
            reasons.add("dose_response_not_modeled")
        all_reasons.update(reasons)
        comparisons.append(
            {
                "ingredient_id": ingredient_id,
                "before": before,
                "after": after,
                "delta_per_day": delta,
                "change": kind,
                "full_withdrawal": kind == "withdrawn",
                "unsupported_reasons": sorted(reasons),
            }
        )
    before_ids = {use.product.product_id for use in change.before}
    after_ids = {use.product.product_id for use in change.after}
    return {
        "schema_version": 1,
        "scope": "supplied_products_per_day",
        "before_products": [_product_payload(use) for use in change.before],
        "after_products": [_product_payload(use) for use in change.after],
        "removed_product_ids": sorted(before_ids - after_ids),
        "added_product_ids": sorted(after_ids - before_ids),
        "retained_product_ids": sorted(before_ids & after_ids),
        "ingredients": comparisons,
        "ranking_eligibility": {
            "eligible": False,
            "unsupported_reasons": sorted(all_reasons),
        },
    }


class UnsupportedProductChangeError(ValueError):
    """A product change has accounting, but no supported health-effect mapping."""

    def __init__(self, change: ProductChange):
        self.accounting = change.to_payload()
        self.unsupported_reasons = tuple(
            self.accounting["ranking_eligibility"]["unsupported_reasons"]
        )
        super().__init__(
            "Product changes cannot be ranked by the catalog effect model: "
            + ", ".join(self.unsupported_reasons)
        )
