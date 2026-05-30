"""Star-allele calling for PGx genes from 23andMe / AncestryDNA raw data.

Limitations (documented rather than hidden):
- ``CYP2D6`` has copy-number variation (*5 deletion, *xN duplications, hybrid
  alleles) that array-based genotyping cannot detect. Calls here cover
  SNP-callable star alleles only; "ultrarapid metabolizer" status from
  gene duplication is invisible to this caller.
- Rare star alleles (<1% frequency in most populations) are omitted from
  the MVP to avoid false-positive calls from chip-specific probe errors.

The algorithm:
1. For each star allele with SNP-defining variants, check whether the
   variant allele is present in either chromosome copy (diploid genotype).
2. Emit the most specific matching pair of alleles as the diplotype.
3. If no variant alleles are present, diplotype is ``*1/*1`` (reference).

Pure-function design: takes a ``calls`` dict (from ``parser``) and returns
a ``Diplotype``. No global state, no network, easy to port to TS/WASM.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .parser import RawGenotype, genotype_at, strand_ambiguous_genotype

_DATA_DIR = Path(__file__).parent / "data"
_PGX_VARIANTS: Optional[dict] = None


def _load_pgx_variants() -> dict:
    global _PGX_VARIANTS
    if _PGX_VARIANTS is None:
        with open(_DATA_DIR / "pgx_variants.json") as f:
            _PGX_VARIANTS = json.load(f)
    return _PGX_VARIANTS


@dataclass(frozen=True)
class Diplotype:
    """Resolved diplotype for a PGx gene (e.g. CYP2D6 \\*1/\\*4).

    ``activity_score`` is the CPIC sum of per-allele activity scores for
    genes that use that system (CYP2D6, CYP3A5). For CYP2C19 and genes
    without activity-score guidance, this is ``None`` and the phenotype
    is derived from function-pair lookup instead.
    """

    gene: str
    allele1: str
    allele2: str
    activity_score: Optional[float] = None
    notes: List[str] = field(default_factory=list)
    callable_variants: int = 0
    missing_variants: int = 0

    @property
    def diplotype(self) -> str:
        return f"{self.allele1}/{self.allele2}"

    @property
    def as_tuple(self) -> tuple[str, str]:
        """Unordered pair for phenotype lookup."""
        return tuple(sorted((self.allele1, self.allele2)))


def _variant_allele_count(
    calls: Dict[str, RawGenotype],
    rsid: str,
    variant_allele: str,
    ref_allele: Optional[str] = None,
) -> Optional[int]:
    """Return 0, 1, or 2 copies of the variant allele; None if uncallable.

    Returns ``None`` for a missing call and for a strand-ambiguous read at a
    palindromic (A/T, C/G) SNP, where containment counting could silently
    invert the result. None of the bundled PGx star-allele variants are
    palindromic (all are C/T or G/A transitions), so this guard is defensive
    rather than active for the current panel.
    """
    g = genotype_at(calls, rsid)
    if g is None:
        return None
    if strand_ambiguous_genotype(g, ref_allele, variant_allele):
        return None
    if len(g) == 1:
        return 1 if g == variant_allele else 0
    return sum(1 for ch in g if ch == variant_allele)


def _call_gene(
    calls: Dict[str, RawGenotype],
    gene: str,
) -> Diplotype:
    """Generic star-allele caller for CYP2D6 / CYP2C19.

    Strategy: iterate defined star alleles in activity-score order, count
    variant allele copies, and deduct from the diploid "budget". Remaining
    copies are reference (``*1``).
    """
    variants = _load_pgx_variants()
    gene_spec = variants[gene]
    alleles_sorted = sorted(
        gene_spec["star_alleles"].items(),
        # Prefer calling no-function alleles first so PM/IM classifications
        # take priority over normal when variant copies overlap.
        key=lambda kv: (
            0 if kv[1]["function"] == "none"
            else 1 if kv[1]["function"] == "decreased"
            else 2 if kv[1]["function"] == "increased"
            else 3
        ),
    )

    variant_copies: List[str] = []
    missing_variants: List[str] = []
    callable_variants = 0
    for allele_name, allele_spec in alleles_sorted:
        if allele_name == "*1":
            continue
        if not allele_spec["defining_variants"]:
            continue
        for defining in allele_spec["defining_variants"]:
            rsid = defining["rsid"]
            variant_allele = defining["variant_allele"]
            count = _variant_allele_count(
                calls, rsid, variant_allele, defining.get("ref_allele")
            )
            if count is None:
                missing_variants.append(f"{allele_name}:{rsid}")
                continue
            callable_variants += 1
            for _ in range(count):
                if len(variant_copies) < 2:
                    variant_copies.append(allele_name)

    notes: List[str] = []
    if callable_variants == 0:
        notes.append(
            f"No {gene} star-allele-defining variants were genotyped; "
            "phenotype is unknown rather than reference."
        )
    elif missing_variants and not variant_copies:
        notes.append(
            f"{gene} reference (*1/*1) cannot be assigned because some "
            "star-allele-defining variants were not genotyped."
        )
    if missing_variants:
        notes.append(
            "Some star-allele-defining variants not genotyped on this chip: "
            + ", ".join(missing_variants[:6])
            + ("" if len(missing_variants) <= 6 else "...")
        )
    for limitation in gene_spec.get("chip_limitations", []):
        notes.append(limitation)

    if callable_variants == 0 or (missing_variants and not variant_copies):
        return Diplotype(
            gene=gene,
            allele1="unknown",
            allele2="unknown",
            activity_score=None,
            notes=notes,
            callable_variants=callable_variants,
            missing_variants=len(missing_variants),
        )

    # Pad with reference alleles to reach diploid.
    while len(variant_copies) < 2:
        variant_copies.append("*1")

    allele1, allele2 = variant_copies[:2]

    # Activity score when applicable.
    activity_score = None
    if gene == "CYP2D6":
        score_lookup = {a: spec["activity_score"]
                        for a, spec in gene_spec["star_alleles"].items()}
        activity_score = (
            score_lookup.get(allele1, 1.0) + score_lookup.get(allele2, 1.0)
        )

    return Diplotype(
        gene=gene,
        allele1=allele1,
        allele2=allele2,
        activity_score=activity_score,
        notes=notes,
        callable_variants=callable_variants,
        missing_variants=len(missing_variants),
    )


def call_cyp2d6(calls: Dict[str, RawGenotype]) -> Diplotype:
    """Call CYP2D6 diplotype from SNP-defined star alleles only.

    Explicitly does NOT detect copy number variation (*5 deletion or *xN
    duplications). An "ultrarapid metabolizer" phenotype from gene
    duplication will be missed; a true CYP2D6*5/*5 deletion will be
    miscalled as *1/*1 or similar. See ``notes`` on the returned
    Diplotype for chip limitations.
    """
    return _call_gene(calls, "CYP2D6")


def call_cyp2c19(calls: Dict[str, RawGenotype]) -> Diplotype:
    """Call CYP2C19 diplotype from SNP-defined star alleles."""
    return _call_gene(calls, "CYP2C19")
