"""Container for genotype-derived decision inputs.

``GeneticProfile`` is attached to ``optiqal.profile.Profile`` via an
optional field. The catalog's ``GeneticEffectRule`` mechanism fires on
``GeneticProfile.phenotypes`` keyed by gene, reweighting per-item HRs.

Building a ``GeneticProfile`` from raw 23andMe data is a one-shot:

    from optiqal.genetics import build_genetic_profile
    gp = build_genetic_profile("~/Downloads/genome_Max_Ghenis_v5.txt")

The ``GeneticProfile`` is pure data — no raw genotypes retained — so it
can safely be passed into the analyzer without risk of leaking the raw
file contents through downstream serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .actionable import (
    ActionableFinding,
    call_apoe,
    call_ashkenazi_brca,
    call_hfe,
)
from .cpic import Phenotype, diplotype_to_phenotype
from .parser import detect_and_parse
from .pgx import Diplotype, call_cyp2c19, call_cyp2d6


@dataclass(frozen=True)
class GeneticProfile:
    """Decision-relevant genetic state — no raw genotypes retained.

    Deliberately does NOT include the raw ``{rsid: RawGenotype}`` dict.
    Pass only high-level derived findings through the simulation layer
    so no call-level data can leak via serialization into protocol-data
    or reports built from ``AnalysisConfig``.
    """

    diplotypes: Dict[str, Diplotype] = field(default_factory=dict)
    phenotypes: Dict[str, Phenotype] = field(default_factory=dict)
    actionable_findings: List[ActionableFinding] = field(default_factory=list)
    ancestry_flags: Dict[str, bool] = field(default_factory=dict)  # e.g. {"ashkenazi_founder_screen": True}
    chip_version: Optional[str] = None

    def has_phenotype(self, gene: str, phenotype: Phenotype) -> bool:
        return self.phenotypes.get(gene) == phenotype

    def has_actionable(self, locus_substring: str) -> bool:
        """True iff any actionable finding's locus contains the substring
        (case-insensitive) and the finding is not absent."""
        needle = locus_substring.lower()
        for f in self.actionable_findings:
            if needle in f.locus.lower() and f.zygosity != "absent":
                return True
        return False


def build_genetic_profile(
    raw_path: str | Path,
    run_ashkenazi_brca: bool = True,
) -> GeneticProfile:
    """Parse a raw genotype file and derive decision-relevant findings.

    ``run_ashkenazi_brca`` controls whether the AJ founder panel is run.
    For non-Ashkenazi users the three variants are rare (<0.01% allele
    frequency in other populations) so a negative result is essentially
    automatic — leaving the check enabled is harmless but can be
    disabled for report clarity.
    """
    calls = detect_and_parse(raw_path)
    diplotypes = {
        "CYP2D6": call_cyp2d6(calls),
        "CYP2C19": call_cyp2c19(calls),
    }
    phenotypes = {
        gene: diplotype_to_phenotype(dp) for gene, dp in diplotypes.items()
    }
    findings: List[ActionableFinding] = []
    findings.extend(call_hfe(calls))
    findings.extend(call_apoe(calls))
    if run_ashkenazi_brca:
        findings.extend(call_ashkenazi_brca(calls))

    return GeneticProfile(
        diplotypes=diplotypes,
        phenotypes=phenotypes,
        actionable_findings=findings,
    )
