"""Map diplotypes to CPIC phenotypes.

The CPIC consortium publishes peer-reviewed diplotype → phenotype →
prescribing-recommendation tables at cpicpgx.org. This module encodes the
phenotype-assignment logic (the upstream half) as a pure dict lookup over
packaged JSON tables, so the catalog's ``GeneticEffectRule`` can fire on
phenotype enums.

Downstream drug-specific dosing recommendations are out of scope for the
MVP — we convert phenotype to a per-drug HR multiplier inside the catalog
rule system rather than reifying CPIC's full Rx guidance table.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Literal, Optional

from .pgx import Diplotype

_DATA_DIR = Path(__file__).parent / "data"
_CPIC: Optional[dict] = None


Phenotype = Literal[
    "poor_metabolizer",
    "intermediate_metabolizer",
    "intermediate_metabolizer_likely",
    "normal_metabolizer",
    "rapid_metabolizer",
    "ultrarapid_metabolizer",
    "unknown",
]


def _load_cpic() -> dict:
    global _CPIC
    if _CPIC is None:
        with open(_DATA_DIR / "cpic_phenotypes.json") as f:
            _CPIC = json.load(f)
    return _CPIC


def _activity_score_phenotype(gene_spec: dict, activity_score: float) -> Phenotype:
    for r in gene_spec["ranges"]:
        if r["min"] <= activity_score <= r["max"]:
            return r["phenotype"]  # type: ignore[return-value]
    return "unknown"


def _function_pair_phenotype(gene_spec: dict, allele1: str, allele2: str) -> Phenotype:
    function_map: Dict[str, str] = gene_spec["function_map"]
    fn1 = function_map.get(allele1, "unknown")
    fn2 = function_map.get(allele2, "unknown")
    if "unknown" in (fn1, fn2):
        return "unknown"
    key = "/".join(sorted([fn1, fn2]))
    pheno = gene_spec["pair_phenotypes"].get(key)
    if pheno is None:
        return "unknown"
    return pheno  # type: ignore[return-value]


def diplotype_to_phenotype(diplotype: Diplotype) -> Phenotype:
    """Assign a CPIC-style phenotype to a diplotype.

    Uses activity-score ranges for CYP2D6 and function-pair lookup for
    CYP2C19. Returns ``"unknown"`` when the gene is unsupported or the
    diplotype can't be classified.
    """
    cpic = _load_cpic()
    gene_spec = cpic.get(diplotype.gene)
    if gene_spec is None:
        return "unknown"

    if gene_spec["mode"] == "activity_score":
        if diplotype.activity_score is None:
            return "unknown"
        return _activity_score_phenotype(gene_spec, diplotype.activity_score)

    if gene_spec["mode"] == "function_pair":
        return _function_pair_phenotype(
            gene_spec, diplotype.allele1, diplotype.allele2,
        )

    return "unknown"


def phenotype_label(gene: str, phenotype: Phenotype) -> str:
    """Human-readable phenotype label for reports."""
    cpic = _load_cpic()
    gene_spec = cpic.get(gene, {})
    if gene_spec.get("mode") == "function_pair":
        return gene_spec.get("pair_labels", {}).get(phenotype, phenotype.replace("_", " ").title())
    for r in gene_spec.get("ranges", []):
        if r["phenotype"] == phenotype:
            return r["label"]
    return phenotype.replace("_", " ").title()
