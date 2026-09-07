# Product-composition accounting

Removing one product can leave the same ingredient in another product. This
module reports the quantities before and after that change. For example, the
synthetic fixtures below contain 5 g of ingredient A in one product and 2.5 g in
another. Removing the first product changes supplied exposure from 7.5 g/day to
2.5 g/day. The result is a partial reduction.

This is deterministic quantity accounting. It supplies no health-effect
estimate, clinical recommendation, or QALY ranking. All examples are synthetic;
they represent no commercial product, personal inventory, lab result, or sleep
record.

## Python interface

```python
from optiqal.product_composition import (
    IngredientAmount, ProductComposition, ProductUse, remove_products,
)

single = ProductUse(ProductComposition(
    "synthetic_single",
    (IngredientAmount("ingredient_a", "5", "g"),),
    composition_complete=True,
    source="Synthetic example",
))
mix = ProductUse(ProductComposition(
    "synthetic_mix",
    (IngredientAmount("ingredient_a", "2500", "mg"),),
    composition_complete=True,
    source="Synthetic example",
))
change = remove_products((single, mix), ("synthetic_single",))
report = change.to_payload()
row = report["ingredients"][0]
assert row["before"]["total_per_day"] == {"amount": "7500", "unit": "mg"}
assert row["after"]["total_per_day"] == {"amount": "2500", "unit": "mg"}
assert row["change"] == "reduced"
assert row["full_withdrawal"] is False
```

`ProductChange(before, after)` compares complete supplied inventories.
`remove_products(inventory, product_ids)` removes specified products.
`replace_product(inventory, product_id, replacement)` substitutes one product
while retaining the other products. To change consumption of the same product,
construct the after inventory with a different `servings_per_day`.

Run all five synthetic keep/remove/replace examples from the repository root:

```bash
cd python
uv run python scripts/product_composition_demo.py > synthetic-accounting.json
```

## Input contract

| Field | Meaning |
| --- | --- |
| `product_id` | Canonical lowercase identity for one product and composition version. A changed composition needs a new ID. |
| `ingredient_id` | Caller-curated identity for the same substance and quantity basis across products. No alias matching occurs. |
| `amount` | Ingredient quantity in **one labeled serving**. Use `None` for an unknown amount; it does not mean zero. |
| `unit` | Label unit, or `None` when unknown. Unknown labels remain in the output. |
| `servings_per_day` | Number of labeled servings in the declared daily comparison, default 1. `None` means unknown; explicit 0 means unused. |
| `composition_complete` | Whether the ingredient list is complete for the product. Defaults to `False`. A partial label can contain additional unlisted ingredients. |
| `source` | Optional provenance text supplied by the caller. The accounting module does not verify a label or source. |

Amounts and serving counts must be finite and nonnegative. Decimal strings are
preferred for preserving source precision. Integers, `Decimal`, and finite
floats are accepted; a float is interpreted through its decimal string. Boolean
values are rejected. Frequency schedules and serving-size inference belong to
the caller; the module performs no weekly-to-daily schedule conversion.

The same physical product must occur once per inventory. Multiple servings use
`servings_per_day`; duplicate product IDs are errors. Repeated ingredient IDs
inside one product are also errors, because label rows can otherwise count the
same constituent twice. Bundle membership and catalog intervention IDs must
not create additional product rows.

Ingredient identity must include the relevant substance, form, and amount basis.
For example, elemental magnesium mass and magnesium-salt mass are not the same
quantity. A probiotic blend and a particular strain must not silently share an
ID. This module cannot detect synonymous IDs or reconcile chemically different
forms. Product-label ingestion must resolve those identities explicitly.

## Units and unknowns

Mass converts to mg: `g` × 1000; `mg` × 1; `mcg`, `ug`, `µg`, and `μg` × 0.001.
`IU` and `CFU` remain separate units. No potency, activity-to-mass, or CFU-to-mass
conversion is inferred. Other unit strings remain visible as unsupported.

All arithmetic uses exact finite-decimal quantities. Totals and deltas serialize
as decimal strings, including scientific notation when appropriate, to avoid
binary floating-point rounding. UI adapters should use a decimal-aware parser
and preserve nonzero amounts when formatting small residuals.

Every ingredient includes:

- `before` and `after`: per-product contributions, `known_totals_per_day`,
  `total_per_day`, incomplete product IDs, and explicit unknown reasons.
- `delta_per_day`: after minus before, or `null` when either total is unknown or
  units are incompatible.
- `change`: `unchanged`, `introduced`, `withdrawn`, `reduced`, `increased`, or
  `unknown`.
- `full_withdrawal`: true only for a known positive before total and a known zero
  after total, within the supplied products.

A known subtotal is never substituted for the total. An unknown amount,
unknown serving count, missing/unsupported unit, or incomplete active product
makes the affected total unknown. A product with an incomplete ingredient list
can retain any unlisted ingredient, so it prevents proving absence even when
its listed ingredients differ. Explicit zero servings contribute no exposure
or uncertainty. Different supported dimensions for one ingredient remain
separate known totals; their common total and delta are `null`.

An entirely unknown product may produce no ingredient rows. Its incomplete
composition remains visible in the product inventory and top-level reasons.
An empty ingredient list therefore does not prove a fully known comparison.
The scope is always `supplied_products_per_day`; diet, unlisted products,
adherence, absorption, and bodily stores are outside the calculation.

## Analysis integration boundary

Clean main's `analyze()` runs catalog simulation and portfolio optimization;
`evaluate_decisions()` evaluates catalog add/drop/adjust decisions. Both now
preflight the optional `Decision.product_change` field before simulation or
ranking. A supplied `ProductChange` raises `UnsupportedProductChangeError`.
The exception carries `.accounting` and `.unsupported_reasons` for an adapter
to display without attaching a health-effect estimate.

Every product report currently has `ranking_eligibility.eligible = false` and
`product_effect_mapping_unavailable`. Known reductions/increases also have
`dose_response_not_modeled`; unknown composition/quantity/unit reasons remain
separate. Even complete physical removal does not establish the catalog model's
starting dose, comparator, duration, population, or multi-ingredient effects.

Legacy catalog-only calls retain their existing behavior and result shape.
They have no product inventory and cannot detect combination-product overlap.
This milestone does not make that existing path safe for product decisions by
itself. In particular, omitting `product_change` loses this guard. The current
protocol state optimizer still operates on catalog IDs, and the web API has no
product-inventory request schema. Neither path is silently populated from
private protocol files, catalog names, or bundle membership.

For the decision-first product owner, the integration sequence is:

1. Collect the full supplied product inventory, serving counts, canonical
   ingredient identities, completeness, and source provenance. Preserve unknowns.
2. Construct a `ProductChange` and display its before/after accounting and
   unsupported reasons. Render partial reductions as partial reductions; never
   translate product removal into full ingredient withdrawal automatically.
3. Pass `product_change` when entering `analyze()`/`evaluate_decisions()` and
   handle the typed exception as an unsupported comparison. Keep these results
   outside QALY, net-value, and recommendation lists.
4. Add a separately reviewed effect-model mapping only when its exact exposure
   contrast is supported. Quantity ratios cannot scale a QALY or hazard estimate.
   Replacements must account for every changed ingredient and retained overlap.

The JSON output uses `schema_version: 1`. Its contract is tested for explicit
unknowns, source/contribution retention, JSON serialization, and the absence of
effect/recommendation fields. This milestone changes no frontend request or
response contract and has no new dependency or provider call.

## Draft branch deployment protection

This branch has an exact `git.deploymentEnabled` exclusion in `vercel.json` so
review pushes do not create automatic previews. Other branches retain their
existing behavior. This uses Vercel's documented
[branch deployment configuration](https://vercel.com/docs/project-configuration/git-configuration#git.deploymentenabled).
