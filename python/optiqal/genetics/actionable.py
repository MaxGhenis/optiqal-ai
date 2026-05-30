"""Actionable-finding lookups — ACMG-SF adjacent variants detectable on chip.

Scope for MVP: HFE (C282Y / H63D), APOE ε2/ε3/ε4 haplotyping, Ashkenazi
Jewish BRCA1/BRCA2 founder mutations. These three are on the 23andMe v5
chip and are directly clinically actionable.

Full ACMG-SF-v3.2 (78-gene secondary findings list) coverage on consumer
microarrays is limited — most pathogenic ACMG variants are rare and not
on the chip. We defer that to a later phase (would need ClinVar bulk
download + ACMG intersect).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .parser import (
    RawGenotype,
    genotype_at,
    is_palindromic_snp,
    strand_ambiguous_genotype,
)

_DATA_DIR = Path(__file__).parent / "data"
_ACTIONABLE: Optional[dict] = None

# Appended to every user-facing significance string. Consumer-chip genotype
# results are screening signals, not diagnoses: they can be wrong (probe
# error, strand/mapping issues, copy-number blind spots) and population risk
# figures do not predict any one person's outcome. Keep this non-prescriptive
# and steer to a qualified clinician / genetic counselor for confirmation.
_CAVEAT = (
    "This is informational, not a diagnosis; consumer-chip results can be "
    "wrong and population risk figures don't predict any individual's "
    "outcome. Confirm with clinical-grade testing and discuss with a "
    "clinician or genetic counselor before acting on it."
)


def _load_actionable() -> dict:
    global _ACTIONABLE
    if _ACTIONABLE is None:
        with open(_DATA_DIR / "actionable_variants.json") as f:
            _ACTIONABLE = json.load(f)
    return _ACTIONABLE


@dataclass(frozen=True)
class ActionableFinding:
    """A pathogenic or clinically-relevant variant detected in raw data.

    ``zygosity`` is ``"heterozygous"``, ``"homozygous"``, or ``"absent"``.
    ``clinical_significance`` is free-text for the report layer.
    """

    locus: str  # e.g. "HFE C282Y" or "BRCA1 185delAG" or "APOE"
    zygosity: str
    clinical_significance: str
    rsid: Optional[str] = None
    genotype: Optional[str] = None
    notes: List[str] = field(default_factory=list)


def _zygosity_at(
    calls: Dict[str, RawGenotype],
    rsid: str,
    variant_allele: str,
    ref_allele: Optional[str] = None,
) -> Optional[str]:
    g = genotype_at(calls, rsid)
    if g is None:
        return None

    # Palindromic-SNP strand guard. For an A/T or C/G locus a call lacking
    # strand annotation cannot be oriented when homozygous: a reverse-strand
    # ref/ref read is identical to a forward-strand alt/alt read, so plain
    # containment counting would silently invert the call. Treat such reads
    # as uncallable. (Heterozygotes carry both alleles and are orientation-
    # invariant, so they remain callable.)
    if strand_ambiguous_genotype(g, ref_allele, variant_allele):
        return None

    variant_symbols = {variant_allele.upper()}
    if variant_allele == "-":
        variant_symbols.add("D")
    if ref_allele == "-":
        variant_symbols.add("I")

    # For single-nucleotide loci (single-base ref AND alt), require every
    # observed allele to be one of {ref, alt}; an allele outside that set is
    # a strand/mapping inconsistency we can't score for containment. Indel
    # loci (``-`` / multi-base alleles, reported as I/D tokens) are exempt.
    if (
        ref_allele
        and len(ref_allele) == 1
        and len(variant_allele) == 1
        and variant_allele != "-"
        and ref_allele != "-"
    ):
        allowed = {variant_allele.upper(), ref_allele.upper()}
        if any(ch not in allowed for ch in g):
            return None

    if len(g) == 1:
        return "homozygous" if g in variant_symbols else "absent"
    count = sum(1 for ch in g if ch in variant_symbols)
    return ("absent", "heterozygous", "homozygous")[count]


def call_hfe(calls: Dict[str, RawGenotype]) -> List[ActionableFinding]:
    """Report C282Y and H63D zygosity.

    Clinical significance derives from the combined diplotype:
    C282Y/C282Y homozygous is the high-penetrance genotype; compound
    heterozygous C282Y/H63D has moderately elevated iron-overload risk;
    single heterozygotes are typically unaffected.
    """
    spec = _load_actionable()["HFE"]
    results: List[ActionableFinding] = []
    c282y_zyg: Optional[str] = None
    h63d_zyg: Optional[str] = None
    for v in spec["variants"]:
        zyg = _zygosity_at(calls, v["rsid"], v["variant_allele"], v.get("ref_allele"))
        if zyg is None:
            continue
        if v["amino_acid"] == "C282Y":
            c282y_zyg = zyg
        elif v["amino_acid"] == "H63D":
            h63d_zyg = zyg

    if c282y_zyg is None and h63d_zyg is None:
        return results

    # Combined interpretation. Phrasing is descriptive, not prescriptive:
    # it characterizes the genotype's typical association and defers any
    # testing/management decision to a clinician via the shared caveat.
    if c282y_zyg == "homozygous":
        sig = "Highest-penetrance HFE genotype for hereditary hemochromatosis. In carriers this is the genotype most associated with iron overload, though many homozygotes never develop clinical disease; iron studies (e.g. ferritin and transferrin saturation) are a common topic to raise with a clinician."
    elif c282y_zyg == "heterozygous" and h63d_zyg in ("heterozygous", "homozygous"):
        sig = "Compound heterozygous (C282Y/H63D). Associated with modestly elevated iron-overload risk on average; a baseline ferritin is something to consider discussing."
    elif c282y_zyg == "heterozygous":
        sig = "C282Y carrier only — typically asymptomatic. Mainly relevant for family planning, since offspring risk rises if a partner also carries an HFE variant."
    elif h63d_zyg == "homozygous":
        sig = "H63D homozygous. Associated with only mildly elevated iron risk and seldom clinically significant on its own."
    else:
        sig = "No pathogenic HFE genotype detected on this panel."

    results.append(
        ActionableFinding(
            locus="HFE (hemochromatosis)",
            zygosity=f"C282Y {c282y_zyg or 'not-called'}, H63D {h63d_zyg or 'not-called'}",
            clinical_significance=f"{sig} {_CAVEAT}",
        )
    )
    return results


def call_apoe(calls: Dict[str, RawGenotype]) -> List[ActionableFinding]:
    """Haplotype APOE from rs429358 + rs7412.

    Genotype mapping (rs429358/rs7412):
      TT/CC → ε3/ε3   (reference)
      TC/CC → ε3/ε4
      CC/CC → ε4/ε4   (highest AD risk)
      TT/TT → ε2/ε2
      TT/CT → ε2/ε3
      TC/CT → ε2/ε4   (ambiguous but functionally treated as this)
    """
    spec = _load_actionable()["APOE"]
    r429 = genotype_at(calls, "rs429358")
    r7412 = genotype_at(calls, "rs7412")
    if r429 is None or r7412 is None:
        return []
    haplotype = spec["haplotypes"].get(f"{r429}/{r7412}")
    if haplotype is None:
        return []

    if haplotype == "e4/e4":
        sig = "Homozygous ε4 — the highest-risk APOE category for late-onset Alzheimer's, with population-average relative risk roughly 10-15× the ε3/ε3 baseline. This is an average across carriers, not a personal forecast; modifiable factors (sleep, exercise, vascular health, DHA, lipid management) still account for much of the variance."
    elif "e4" in haplotype:
        sig = "One ε4 allele — population-average AD risk around ~3× the ε3/ε3 baseline. A moderate average effect that doesn't, on its own, dictate changes to a sleep/exercise/lipid-focused routine."
    elif haplotype == "e2/e2":
        sig = "Homozygous ε2 — associated on average with lower AD risk, but ε2/ε2 carries its own type-III hyperlipoproteinemia risk that can be worth monitoring."
    elif "e2" in haplotype:
        sig = "One ε2 allele — associated with modest average AD protection."
    else:
        sig = "ε3/ε3 (reference) — population-baseline AD risk."

    return [
        ActionableFinding(
            locus="APOE",
            zygosity=haplotype,
            clinical_significance=f"{sig} {_CAVEAT}",
        )
    ]


def call_ashkenazi_brca(calls: Dict[str, RawGenotype]) -> List[ActionableFinding]:
    """Check the 3 Ashkenazi founder BRCA mutations.

    Note: these are the specific founder mutations on the 23andMe v5 chip.
    A negative result on this panel does NOT rule out hereditary
    cancer-risk syndromes broadly; a clinical panel (Color, Invitae) is
    required for comprehensive BRCA1/2 + Lynch + PALB2 coverage.
    """
    spec = _load_actionable()["BRCA_ASHKENAZI"]
    results: List[ActionableFinding] = []
    any_called = False
    for v in spec["variants"]:
        zyg = _zygosity_at(calls, v["rsid"], v["variant_allele"], v.get("ref_allele"))
        if zyg is None:
            continue
        any_called = True
        if zyg == "absent":
            continue
        sig = (
            f"Pathogenic {v['gene']} {v['mutation']} {zyg}. "
            f"Genetic counseling can help interpret what this means for "
            f"screening and risk-reduction options in your situation. "
            f"{v['notes']} {_CAVEAT}"
        )
        results.append(
            ActionableFinding(
                locus=f"{v['gene']} {v['mutation']}",
                zygosity=zyg,
                clinical_significance=sig,
                rsid=v["rsid"],
            )
        )

    if any_called and not results:
        results.append(
            ActionableFinding(
                locus="BRCA Ashkenazi panel",
                zygosity="absent",
                clinical_significance=(
                    "All three Ashkenazi founder mutations absent. This rules out "
                    "the common founder variants but does NOT exclude rarer "
                    "pathogenic BRCA1/2 or other hereditary-cancer variants. A "
                    "clinical-grade panel (e.g. Color, Invitae) gives more "
                    "comprehensive coverage, and a genetic counselor can advise "
                    "whether that's worthwhile given family history. " + _CAVEAT
                ),
            )
        )
    return results
