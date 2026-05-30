"""Render GeneticProfile → Markdown report for Obsidian vault.

Report stays local. Nothing uploaded. Rendered sections:

1. Pharmacogenomics summary (diplotype → phenotype per gene)
2. Actionable findings (HFE, APOE, BRCA-AJ)
3. Per-item stack adjustments (which catalog items saw HR multipliers)
4. Caveats and chip limitations surfaced from the PGx caller

Matches the same pure-function style as the rest of the module so a
future TS port can mirror the structure.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, List, Optional

from .cpic import phenotype_label
from .profile import GeneticProfile


def _section(title: str, body: Iterable[str]) -> str:
    lines = list(body)
    if not lines:
        return ""
    return f"## {title}\n\n" + "\n".join(lines) + "\n"


def _render_input_summary(gp: GeneticProfile) -> str:
    summary = gp.source_summary
    if summary is None:
        return ""
    lines = [
        f"- **Source file**: {summary.source_name}",
        f"- **Format**: {summary.format_name} ({summary.compression})",
        f"- **Parsed genotype calls**: {summary.call_count:,}",
    ]
    if summary.selected_member:
        lines.append(f"- **ZIP member used**: {summary.selected_member}")
    if summary.chip_version:
        lines.append(f"- **Detected chip version**: {summary.chip_version}")
    return _section("Input summary", lines)


def _marker_coverage(dp) -> str:
    total = dp.callable_variants + dp.missing_variants
    if total == 0:
        return "—"
    return f"{dp.callable_variants}/{total}"


def _join_notes(notes: List[str]) -> str:
    return "; ".join(note.rstrip(".") for note in notes[:2])


def _render_pgx(gp: GeneticProfile) -> str:
    if not gp.diplotypes:
        return ""
    rows: List[str] = [
        "| Gene | Marker coverage | Diplotype | Phenotype | Activity score | Notes |",
        "|---|---:|---|---|---:|---|",
    ]
    for gene, dp in gp.diplotypes.items():
        pheno = gp.phenotypes.get(gene, "unknown")
        label = phenotype_label(gene, pheno)
        score = f"{dp.activity_score:.1f}" if dp.activity_score is not None else "—"
        caveats = _join_notes(dp.notes) if dp.notes else ""
        rows.append(
            f"| {gene} | {_marker_coverage(dp)} | {dp.diplotype} | "
            f"{label} | {score} | {caveats} |"
        )
    return _section("Pharmacogenomics", rows)


def _render_actionable(gp: GeneticProfile) -> str:
    if not gp.actionable_findings:
        return ""
    out: List[str] = []
    for f in gp.actionable_findings:
        out.append(f"### {f.locus}")
        out.append("")
        out.append(f"- **Genotype**: {f.zygosity}")
        out.append(f"- **Clinical significance**: {f.clinical_significance}")
        if f.notes:
            for note in f.notes:
                out.append(f"- {note}")
        out.append("")
    return _section("Actionable findings", out)


def _render_caveats(gp: GeneticProfile) -> str:
    bullets: List[str] = [
        (
            "- Consumer microarrays (23andMe / AncestryDNA) genotype only the "
            "specific SNPs on the chip. Absence of a pathogenic variant on "
            "this panel does NOT exclude rare variants of the same gene."
        ),
        (
            "- CYP2D6 copy number variants (\\*5 deletion, \\*xN duplications "
            "causing true ultrarapid metabolism) are NOT callable from array "
            "data. PGx calls are tentative in this class."
        ),
        (
            "- For comprehensive coverage consider clinical whole-genome "
            "sequencing or targeted clinical panels (Color Health, Invitae) "
            "with genetic-counselor support."
        ),
    ]
    # Pull gene-specific limitations into the caveat list.
    for gene, dp in gp.diplotypes.items():
        if dp.notes:
            bullets.append(f"- **{gene}**: {dp.notes[0]}")
    return _section("Caveats and chip limitations", bullets)


def _render_header(gp: GeneticProfile) -> str:
    today = date.today().isoformat()
    privacy_note = (
        "Generated locally from consumer genotype data. No raw genotypes "
        "retained in this report — only derived diplotypes and phenotypes. "
        "Do not publish this file."
    )
    return f"""---
date: {today}
tags: [health, genetics, pgx]
status: ongoing
sensitivity: private
publishable: false
---

# Genetic profile report

{privacy_note}

"""


def render_markdown_report(
    gp: GeneticProfile,
    adjustments: Optional[List[str]] = None,
) -> str:
    """Render a ``GeneticProfile`` to a Markdown string.

    ``adjustments`` is an optional list of pre-formatted strings describing
    which catalog items were reweighted by this profile's genetic rules.
    Caller can build these from ``analyze()`` output and pass them in.
    """
    parts = [
        _render_header(gp),
        _render_input_summary(gp),
        _render_pgx(gp),
        _render_actionable(gp),
    ]
    if adjustments is not None:
        parts.append(
            _section(
                "Stack adjustments from PGx",
                adjustments or ["- None. No catalog genetic rules matched."],
            )
        )
    parts.append(_render_caveats(gp))
    # Drop empty sections and join.
    return "\n".join(p for p in parts if p)
