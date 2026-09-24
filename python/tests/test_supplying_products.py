"""Product mappings must not make standalone sleep items disappear by row order."""

import sqlite3
from itertools import permutations

from optiqal.protocol_ground_up import resolve_supplying_products
from optiqal.sleep_stack import select_sleep_stack_universe


def test_catalog_mapping_row_order_preserves_sleep_stack_universe():
    """A separate glycine bottle cannot rename the entire Longevity Mix bundle."""
    rows = (
        ("glycine_2g", "Glycine 2g (NOW)"),
        ("creatine_5g", "Standalone creatine"),
        ("hyaluronic_acid_120", "Blueprint Longevity Mix"),
    )
    state_ids = [
        "glycine_2g",
        "creatine_5g",
        "hyaluronic_acid_120",
        "l_theanine_200",
        "caakg_2000",
        "trazodone_50mg",
    ]
    protocol_items = [{"id": item_id, "status": "taking"} for item_id in state_ids]
    estimates = {item_id: {} for item_id in state_ids}
    first_result = None

    for order in permutations(rows):
        # Exercise actual SQLite insertion/iteration order without a disk DB.
        with sqlite3.connect(":memory:") as conn:
            conn.execute(
                "CREATE TABLE catalog_product_mappings "
                "(catalog_id TEXT, product_name TEXT)"
            )
            conn.executemany(
                "INSERT INTO catalog_product_mappings VALUES (?, ?)", order
            )
            baseline = {
                "supplying_products": dict(
                    conn.execute(
                        "SELECT catalog_id, product_name FROM catalog_product_mappings"
                    )
                )
            }

        supplying = resolve_supplying_products(baseline, state_ids)
        assert supplying["glycine_2g"] == "Glycine 2g (NOW)"
        assert supplying["creatine_5g"] == "Standalone creatine"
        assert supplying["l_theanine_200"] == "Blueprint Longevity Mix"
        assert supplying["caakg_2000"] == "Blueprint Longevity Mix"

        result = select_sleep_stack_universe(
            protocol_items, estimates, baseline=baseline
        )
        assert result[0] == ["glycine_2g", "trazodone_50mg"]
        if first_result is None:
            first_result = result
        else:
            assert result == first_result
