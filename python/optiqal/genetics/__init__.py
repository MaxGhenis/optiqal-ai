"""Genetics module for Optiqal — PGx + actionable-findings layer.

Local-only: parses 23andMe (and compatible AncestryDNA) raw genotyping
files, calls pharmacogenomic star alleles via CPIC tables, identifies
actionable variants (HFE, APOE, Ashkenazi BRCA founders), and exposes a
``GeneticProfile`` that plugs into ``optiqal.profile.Profile`` so the
catalog's ``GeneticEffectRule`` mechanism can reweight per-item HRs.

Privacy: no data leaves the local machine. The only network call is an
optional one-time CPIC table refresh from ``cpicpgx.org`` (checksummed).
Reports render as Markdown for Obsidian — never uploaded.
"""

from .parser import (
    RawGenotype,
    parse_23andme,
    parse_ancestry,
)
from .pgx import (
    Diplotype,
    call_cyp2d6,
    call_cyp2c19,
)
from .cpic import (
    Phenotype,
    diplotype_to_phenotype,
)
from .actionable import (
    ActionableFinding,
    call_apoe,
    call_hfe,
    call_ashkenazi_brca,
)
from .profile import GeneticProfile, build_genetic_profile
from .rules import GeneticEffectRule
from .reports import render_markdown_report

__all__ = [
    "RawGenotype",
    "parse_23andme",
    "parse_ancestry",
    "Diplotype",
    "call_cyp2d6",
    "call_cyp2c19",
    "Phenotype",
    "diplotype_to_phenotype",
    "ActionableFinding",
    "call_apoe",
    "call_hfe",
    "call_ashkenazi_brca",
    "GeneticProfile",
    "build_genetic_profile",
    "GeneticEffectRule",
    "render_markdown_report",
]
