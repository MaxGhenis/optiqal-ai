"""Property tests for product-composition accounting (synthetic inputs only)."""

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from optiqal.product_composition import (
    IngredientAmount,
    ProductComposition,
    ProductUse,
    remove_products,
)

TO_MG = {"mg": Decimal(1), "g": Decimal(1000), "mcg": Decimal("0.001")}

amounts = st.decimals(
    min_value=Decimal("0.001"), max_value=Decimal("10000"), places=3
).map(lambda d: format(d.normalize(), "f"))
products = st.lists(
    st.tuples(amounts, st.sampled_from(sorted(TO_MG)), st.integers(1, 4)),
    min_size=1,
    max_size=6,
)


def _inventory(rows):
    return tuple(
        ProductUse(
            ProductComposition(
                f"synthetic_{i}",
                (IngredientAmount("ingredient_a", amount, unit),),
                composition_complete=True,
                source="synthetic property-test fixture",
            ),
            servings_per_day=servings,
        )
        for i, (amount, unit, servings) in enumerate(rows)
    )


def _mg(total):
    assert total["unit"] == "mg"
    return Decimal(total["amount"])


@settings(max_examples=200, deadline=None)
@given(rows=products, data=st.data())
def test_before_plus_delta_equals_after_and_totals_are_exact(rows, data):
    """For known inventories: each total is the exact sum of amount x servings,
    before + delta = after, and removing everything is a full withdrawal."""
    inventory = _inventory(rows)
    removed = data.draw(
        st.sets(st.sampled_from([u.product.product_id for u in inventory]))
    )
    row = remove_products(inventory, sorted(removed)).to_payload()["ingredients"][0]
    expected = {
        u.product.product_id: Decimal(amount) * TO_MG[unit] * servings
        for u, (amount, unit, servings) in zip(inventory, rows)
    }
    before = _mg(row["before"]["total_per_day"])
    assert before == sum(expected.values())
    kept = [pid for pid in expected if pid not in removed]
    if kept:
        after = _mg(row["after"]["total_per_day"])
        assert after == sum(expected[pid] for pid in kept)
    else:
        after = Decimal(0)
        assert row["full_withdrawal"] is True
    delta = Decimal(row["delta_per_day"]["amount"]) if row["delta_per_day"] else 0
    assert before + delta == after
