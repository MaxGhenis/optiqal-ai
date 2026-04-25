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

from .parser import RawGenotype, genotype_at

_DATA_DIR = Path(__file__).parent / "data"
_ACTIONABLE: Optional[dict] = None


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
    variant_symbols = {variant_allele.upper()}
    if variant_allele == "-":
        variant_symbols.add("D")
    if ref_allele == "-":
        variant_symbols.add("I")
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

    # Combined interpretation.
    if c282y_zyg == "homozygous":
        sig = "High-penetrance genotype for hereditary hemochromatosis. Recommend ferritin + transferrin saturation screening; typical follow-up protocol applies."
    elif c282y_zyg == "heterozygous" and h63d_zyg in ("heterozygous", "homozygous"):
        sig = "Compound heterozygous (C282Y/H63D). Modestly elevated iron-overload risk; baseline ferritin worth checking."
    elif c282y_zyg == "heterozygous":
        sig = "C282Y carrier only — typically asymptomatic. Relevant for family planning (offspring risk if partner also carries)."
    elif h63d_zyg == "homozygous":
        sig = "H63D homozygous. Mildly elevated iron risk; ferritin check reasonable but unlikely to be clinically significant alone."
    else:
        sig = "No pathogenic HFE genotype detected."

    results.append(
        ActionableFinding(
            locus="HFE (hemochromatosis)",
            zygosity=f"C282Y {c282y_zyg or 'not-called'}, H63D {h63d_zyg or 'not-called'}",
            clinical_significance=sig,
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
        sig = "Homozygous ε4 — highest genetic risk category for late-onset Alzheimer's (roughly 10-15× baseline). Modifiable risk factors (sleep, exercise, vascular health, DHA, lipid optimization) still explain the bulk of variance."
    elif "e4" in haplotype:
        sig = "One ε4 allele — ~3× baseline AD risk. Moderate effect size; doesn't change the optimization stack meaningfully given existing sleep + exercise + lipid focus."
    elif haplotype == "e2/e2":
        sig = "Homozygous ε2 — protective against AD, but ε2/ε2 carries its own type-III hyperlipoproteinemia risk worth monitoring."
    elif "e2" in haplotype:
        sig = "One ε2 allele — modest AD protection."
    else:
        sig = "ε3/ε3 (reference). Baseline AD risk."

    return [
        ActionableFinding(
            locus="APOE",
            zygosity=haplotype,
            clinical_significance=sig,
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
            f"Warrants genetic counseling consultation; screening cadence and risk-reducing discussion are standard of care. "
            f"{v['notes']}"
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
                    "pathogenic BRCA1/2 or other hereditary-cancer variants. For "
                    "comprehensive coverage use a clinical panel (Color, Invitae)."
                ),
            )
        )
    return results
