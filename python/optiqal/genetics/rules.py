"""Catalog-level hook for genotype-aware HR multipliers.

A ``GeneticEffectRule`` declares: "when phenotype X is present, multiply
log(HR) by this factor." The multiplier of 1.0 is a no-op; <1.0 shrinks
toward null (weaker effect); >1.0 amplifies (stronger effect — rare but
valid for genuine UM → enhanced prodrug activation scenarios).

Design principle: keep rules expressive enough for CPIC guidance but
simple enough to port to TS. A rule fires if-and-only-if the profile
has the matching gene/phenotype; no multi-gene combinations (yet). Most
CPIC recommendations are single-gene anyway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .cpic import Phenotype
from .profile import GeneticProfile


@dataclass(frozen=True)
class GeneticEffectRule:
    """Genotype-conditioned multiplier on an intervention's log(HR).

    ``multiplier`` follows the same convention as ``ProfileEffectRule``:
    ``hr_adjusted = exp(log(hr) * multiplier)``. A value of ``0.3`` means
    "only 30% of the observed effect is expected in this genotype" —
    appropriate for, e.g., trazodone in CYP2D6 ultrarapid metabolizers
    where the parent compound clears too fast to sustain the therapeutic
    effect.

    Optional ``rationale`` is shown in the report so the user can see
    why a given item's HR shifted.
    """

    gene: str
    phenotype: Phenotype
    multiplier: float
    rationale: str = ""

    def matches(self, genetic_profile: Optional[GeneticProfile]) -> bool:
        if genetic_profile is None:
            return False
        return genetic_profile.has_phenotype(self.gene, self.phenotype)
