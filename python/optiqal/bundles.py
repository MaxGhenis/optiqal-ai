"""
Product bundle definitions.

Maps catalog item IDs to purchasable products, enabling bundle-vs-separate
cost analysis. Items with annual_cost=0 in the catalog are typically bundled.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Bundle:
    """A purchasable product containing multiple catalog items."""

    id: str
    name: str
    annual_cost: float  # USD/yr
    item_ids: tuple  # CatalogEntry IDs in this bundle (tuple for frozen)

    @property
    def monthly_cost(self) -> float:
        return self.annual_cost / 12


BUNDLES: Dict[str, Bundle] = {}


def _add(bundle: Bundle) -> None:
    BUNDLES[bundle.id] = bundle


_add(Bundle(
    "blueprint_essential_capsules",
    "Blueprint Essential Capsules",
    588,  # $49/mo
    (
        "vitamin_d_2000", "nr_300", "fisetin_100", "boron_3",
        "lithium_1mg_orotate", "spermidine_10", "luteolin_100",
        "broccoli_seed_200", "ubiquinol_50",
    ),
))
_add(Bundle(
    "blueprint_advanced_antioxidants",
    "Blueprint Advanced Antioxidants",
    588,  # $49/mo
    (
        "vitamin_k2", "lutein_zeaxanthin", "astaxanthin_12", "lycopene_15",
    ),
))
_add(Bundle(
    "blueprint_longevity_mix",
    "Blueprint Longevity Mix",
    588,  # $49/mo
    (
        "creatine_5g", "magnesium_200", "hyaluronic_acid_120",
        # Also contains partial doses of taurine (1500mg), glycine (1200mg),
        # CaAKG (2000mg), L-Lysine (1000mg), Glucosamine (750mg),
        # Glutathione (250mg), L-Theanine (200mg), Vitamin C (250mg)
    ),
))
_add(Bundle(
    "blueprint_nac_ginger_curcumin",
    "Blueprint NAC+Ginger+Curcumin",
    324,  # $27/mo
    (
        "nac_1200", "ginger_400", "curcumin_250",
    ),
))


def get_item_to_bundle_map() -> Dict[str, str]:
    """Return mapping from catalog item ID to bundle ID."""
    result = {}
    for bundle in BUNDLES.values():
        for item_id in bundle.item_ids:
            result[item_id] = bundle.id
    return result


def recommend_bundles(
    selected_ids: List[str],
    item_results: Dict[str, dict],
    horizon_years: float = 40,
) -> List[dict]:
    """
    Analyze which bundles are worth buying given selected items.

    For each bundle, computes:
    - Which selected items it contains
    - Combined gross value of those items
    - Whether the bundle is worth buying vs cost

    Args:
        selected_ids: IDs of items selected by portfolio optimizer
        item_results: Per-item simulation results keyed by ID
        horizon_years: Planning horizon for total cost

    Returns:
        List of dicts with bundle analysis, sorted by net value
    """
    selected_set = set(selected_ids)
    results = []

    for bundle in BUNDLES.values():
        overlap = [iid for iid in bundle.item_ids if iid in selected_set]
        if not overlap:
            continue

        value_sum = sum(
            item_results[iid]["gross_value"]
            for iid in overlap
            if iid in item_results
        )
        total_cost = bundle.annual_cost * horizon_years
        net = value_sum - total_cost
        worth_it = value_sum > total_cost

        results.append({
            "bundle_id": bundle.id,
            "bundle_name": bundle.name,
            "annual_cost": bundle.annual_cost,
            "total_cost": total_cost,
            "selected_items": overlap,
            "n_selected": len(overlap),
            "n_total": len(bundle.item_ids),
            "combined_value": value_sum,
            "net_value": net,
            "worth_it": worth_it,
        })

    results.sort(key=lambda x: x["net_value"], reverse=True)
    return results
