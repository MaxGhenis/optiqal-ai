#!/usr/bin/env python3
"""Print deterministic synthetic product comparisons. No records or providers."""

from __future__ import annotations

import json
import sys

from optiqal.product_composition import (
    IngredientAmount,
    ProductChange,
    ProductComposition,
    ProductUse,
    remove_products,
    replace_product,
)


def synthetic_examples() -> dict:
    """Fixtures illustrate accounting only; these are not commercial products."""
    source = "Synthetic composition fixture; no commercial product or personal data"
    single = ProductUse(
        ProductComposition(
            "synthetic_single",
            (IngredientAmount("ingredient_a", "5", "g"),),
            composition_complete=True,
            source=source,
        )
    )
    mix = ProductUse(
        ProductComposition(
            "synthetic_mix",
            (
                IngredientAmount("ingredient_a", "2500", "mg"),
                IngredientAmount("ingredient_b", "100", "mg"),
            ),
            composition_complete=True,
            source=source,
        )
    )
    replacement = ProductUse(
        ProductComposition(
            "synthetic_replacement",
            (IngredientAmount("ingredient_a", "1", "g"),),
            composition_complete=True,
            source=source,
        )
    )
    unknown = ProductUse(
        ProductComposition(
            "synthetic_unknown_amount",
            (IngredientAmount("ingredient_a", None, "mg"),),
            composition_complete=True,
            source=source,
        )
    )
    inventory = (single, mix)
    changes = {
        "keep": ProductChange(inventory, inventory),
        "remove_one": remove_products(inventory, (single.product.product_id,)),
        "remove_all": remove_products(
            inventory, (single.product.product_id, mix.product.product_id)
        ),
        "replace_one": replace_product(
            inventory, single.product.product_id, replacement
        ),
        "retain_unknown_amount": remove_products(
            (single, unknown), (single.product.product_id,)
        ),
    }
    return {
        "data_source": source,
        "examples": {name: change.to_payload() for name, change in changes.items()},
    }


def main() -> int:
    json.dump(synthetic_examples(), sys.stdout, indent=2, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
