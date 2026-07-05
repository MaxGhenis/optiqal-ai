"""Genetics module for Optiqal — PGx + actionable-findings layer.

Local-only: parses 23andMe (and compatible AncestryDNA) raw genotyping
files, calls pharmacogenomic star alleles via CPIC tables, identifies
actionable variants (HFE, APOE, Ashkenazi BRCA founders), and exposes a
``GeneticProfile`` that plugs into ``optiqal.profile.Profile`` so the
catalog's ``GeneticEffectRule`` mechanism can reweight per-item HRs.

Privacy: no data leaves the local machine. The module makes no network
calls; CPIC and variant tables are bundled locally under ``genetics/data/``.
Reports render as Markdown for Obsidian — never uploaded.
"""

from .actionable import (
    ActionableFinding,
    call_apoe,
    call_ashkenazi_brca,
    call_hfe,
)
from .cpic import (
    Phenotype,
    diplotype_to_phenotype,
)
from .parser import (
    GenotypeFileSummary,
    RawGenotype,
    parse_23andme,
    parse_ancestry,
    summarize_genotype_file,
)
from .pgx import (
    Diplotype,
    call_cyp2c19,
    call_cyp2d6,
)
from .profile import GeneticProfile, build_genetic_profile
from .reports import render_markdown_report
from .rules import GeneticEffectRule

__all__ = [
    "RawGenotype",
    "GenotypeFileSummary",
    "parse_23andme",
    "parse_ancestry",
    "summarize_genotype_file",
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
