"""
Intervention Catalog — structured database of supplements and interventions.

Each entry contains literature-derived hazard ratios, confounding priors,
costs, QoL modifiers, and source notes. All HRs are pre-publication-bias-
correction (raw observed values from studies).

Use with `publication_bias_correct()` from `confounding.py` before simulation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

import numpy as np

from .confounding import ConfoundingPrior, publication_bias_correct
from .intervention import Distribution, Intervention, MortalityEffect


@dataclass(frozen=True)
class CatalogEntry:
    """A single intervention in the catalog."""

    id: str
    name: str
    category: Literal[
        "rx_current", "rx_candidate", "supplement_current",
        "supplement_bought", "supplement_candidate",
    ]
    hr_observed: float  # Raw observed HR from literature (before pub bias correction)
    log_sd: float  # Uncertainty in log(HR)
    conf_alpha: float  # Beta prior alpha for causal fraction
    conf_beta: float  # Beta prior beta for causal fraction
    annual_cost: float  # Annual cost in USD
    qol_annual: float = 0.0  # Annual QoL effect in QALYs (non-mortality)
    notes: str = ""
    sources: List[str] = field(default_factory=list)

    def to_intervention(
        self,
        pub_bias_shrinkage: float = 0.30,
    ) -> Intervention:
        """Convert to an Intervention object with publication bias correction."""
        hr = publication_bias_correct(self.hr_observed, pub_bias_shrinkage)
        return Intervention(
            id=self.id,
            name=self.name,
            category="diet",  # Generic; actual confounding prior is explicit
            mortality=MortalityEffect(
                hazard_ratio=Distribution(
                    type="lognormal",
                    params={"log_mean": np.log(hr), "log_sd": self.log_sd},
                ),
            ),
            confounding_prior=ConfoundingPrior(
                alpha=self.conf_alpha, beta=self.conf_beta,
            ),
        )


# =============================================================================
# CATALOG
# =============================================================================

CATALOG: Dict[str, CatalogEntry] = {}


def _add(entry: CatalogEntry) -> None:
    CATALOG[entry.id] = entry


# ---------------------------------------------------------------------------
# Prescriptions — current
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "finasteride_1.25mg", "Finasteride 1.25mg", "rx_current",
    hr_observed=0.93, log_sd=0.10, conf_alpha=4.0, conf_beta=2.5,
    annual_cost=171,  # $14.99 / (8*4 doses) * 365 = $171/yr
    qol_annual=0.015,
    notes="PCPT RCT n=18882. Hair preservation.",
))
_add(CatalogEntry(
    "tadalafil_2.5mg", "Tadalafil 2.5mg", "rx_current",
    hr_observed=0.88, log_sd=0.15, conf_alpha=2.0, conf_beta=4.0,
    annual_cost=252,  # $20.72 / 30 * 365 = $252/yr
    qol_annual=0.020,
    notes="Anderson 2016 obs HR 0.67. Endothelial RCTs.",
))
_add(CatalogEntry(
    "trazodone_50mg", "Trazodone 50mg", "rx_current",
    hr_observed=1.00, log_sd=0.05, conf_alpha=3.0, conf_beta=3.0,
    annual_cost=223,  # $18.34 / 30 * 365 = $223/yr
    qol_annual=0.010,
    notes="Sleep maintenance. No mortality data.",
))

# ---------------------------------------------------------------------------
# Prescriptions — candidates (off-label longevity)
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "rapamycin_5mg_wk", "Rapamycin 5mg/wk", "rx_candidate",
    hr_observed=0.85, log_sd=0.20, conf_alpha=2.0, conf_beta=3.0,
    annual_cost=600, qol_annual=-0.003,
    notes="ITP mice: +26% median lifespan. Mannick 2014. Immunosuppression risk.",
))
_add(CatalogEntry(
    "metformin_500mg", "Metformin 500mg", "rx_candidate",
    hr_observed=0.90, log_sd=0.12, conf_alpha=2.5, conf_beta=3.5,
    annual_cost=48, qol_annual=0.000,
    notes="Bannister 2014: diabetics on metformin outlived controls. TAME pending.",
))
_add(CatalogEntry(
    "acarbose_50mg", "Acarbose 50mg", "rx_candidate",
    hr_observed=0.88, log_sd=0.18, conf_alpha=2.0, conf_beta=4.0,
    annual_cost=120, qol_annual=-0.005,
    notes="ITP mice: +22% median lifespan (males). GI side effects.",
))
_add(CatalogEntry(
    "aspirin_81mg", "Low-dose aspirin 81mg", "rx_candidate",
    hr_observed=0.94, log_sd=0.06, conf_alpha=4.0, conf_beta=2.0,
    annual_cost=15, qol_annual=-0.001,
    notes="ASPREE (>70yr): no benefit, more bleeding. USPSTF equivocal at 39.",
))
_add(CatalogEntry(
    "semaglutide", "GLP-1 RA (semaglutide)", "rx_candidate",
    hr_observed=0.80, log_sd=0.12, conf_alpha=3.5, conf_beta=2.0,
    annual_cost=6000, qol_annual=0.010,
    notes="SELECT trial: HR 0.80 MACE. Weight loss. Expensive, GI effects.",
))
_add(CatalogEntry(
    "lithium_5mg", "Low-dose lithium 5mg", "rx_candidate",
    hr_observed=0.92, log_sd=0.18, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.001,
    notes="Ecological: municipal Li → lower suicide/dementia. No RCTs at low dose.",
))
_add(CatalogEntry(
    "17a_estradiol", "17α-estradiol (topical)", "rx_candidate",
    hr_observed=0.88, log_sd=0.20, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=360, qol_annual=-0.002,
    notes="ITP mice: +19% median lifespan (males only). No human data.",
))
_add(CatalogEntry(
    "empagliflozin", "SGLT2i (empagliflozin)", "rx_candidate",
    hr_observed=0.86, log_sd=0.10, conf_alpha=3.5, conf_beta=2.5,
    annual_cost=3600, qol_annual=0.002,
    notes="EMPA-REG: HR 0.68 CV death (diabetics). Off-label in healthy unclear.",
))
_add(CatalogEntry(
    "statin_5mg", "Statin (rosuvastatin 5mg)", "rx_candidate",
    hr_observed=0.88, log_sd=0.08, conf_alpha=4.5, conf_beta=1.5,
    annual_cost=120, qol_annual=-0.002,
    notes="CTT meta: 21% CVD reduction per mmol/L LDL. LDL already 64.",
))

# ---------------------------------------------------------------------------
# Supplements — current stack
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "omega3_clo", "Omega-3 CLO ~500mg", "supplement_current",
    hr_observed=0.92, log_sd=0.10, conf_alpha=2.5, conf_beta=3.5,
    annual_cost=180, qol_annual=0.001,
    notes="Aung 2018 meta. VITAL.",
))
_add(CatalogEntry(
    "vitamin_d_2000", "Vitamin D 2000 IU", "supplement_current",
    hr_observed=0.94, log_sd=0.08, conf_alpha=3.0, conf_beta=4.0,
    annual_cost=30, qol_annual=0.000,
    notes="VITAL NS. Bolland meta D3 HR 0.97.",
))
_add(CatalogEntry(
    "magnesium_200", "Magnesium 200mg", "supplement_current",
    hr_observed=0.90, log_sd=0.12, conf_alpha=2.0, conf_beta=3.5,
    annual_cost=120, qol_annual=0.005,
    notes="Fang meta. BP RCTs.",
))
_add(CatalogEntry(
    "garlic_1200", "Garlic 1200mg", "supplement_current",
    hr_observed=0.88, log_sd=0.12, conf_alpha=2.0, conf_beta=4.0,
    annual_cost=300, qol_annual=0.000,
    notes="Obs HR 0.88. BP + calcification RCTs.",
))
_add(CatalogEntry(
    "creatine_5g", "Creatine 5g", "supplement_current",
    hr_observed=0.98, log_sd=0.08, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=120, qol_annual=0.005,
    notes="Muscle/cognitive RCTs. No mortality.",
))
_add(CatalogEntry(
    "nac_1200", "NAC 1200mg", "supplement_current",
    hr_observed=0.93, log_sd=0.15, conf_alpha=1.5, conf_beta=4.0,
    annual_cost=40, qol_annual=0.001,
    notes="Critical care RCTs. Glutathione precursor.",
))
_add(CatalogEntry(
    "curcumin_250", "Curcumin 250mg", "supplement_current",
    hr_observed=0.90, log_sd=0.18, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=40, qol_annual=0.000,
    notes="Anti-inflam. Bioavailability issues.",
))
_add(CatalogEntry(
    "ginger_400", "Ginger 400mg", "supplement_current",
    hr_observed=0.96, log_sd=0.15, conf_alpha=1.0, conf_beta=5.0,
    annual_cost=0, qol_annual=0.000,
    notes="Bundled. Anti-nausea.",
))
_add(CatalogEntry(
    "vitamin_k2", "Vitamin K2 MK-7+MK-4", "supplement_current",
    hr_observed=0.92, log_sd=0.15, conf_alpha=1.5, conf_beta=4.0,
    annual_cost=25, qol_annual=0.000,
    notes="Rotterdam obs. Calcification RCTs.",
))
_add(CatalogEntry(
    "melatonin_300mcg", "Melatonin 300mcg", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.2, conf_beta=4.5,
    annual_cost=30, qol_annual=0.008,
    notes="Sleep onset RCTs.",
))
_add(CatalogEntry(
    "collagen_22g", "Collagen 22g", "supplement_current",
    hr_observed=0.99, log_sd=0.05, conf_alpha=1.0, conf_beta=7.0,
    annual_cost=360, qol_annual=0.003,
    notes="No mortality data. Joint/skin RCTs.",
))
_add(CatalogEntry(
    "prebiotics", "Prebiotics combo", "supplement_current",
    hr_observed=0.96, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=180, qol_annual=0.003,
    notes="Gut health markers.",
))
_add(CatalogEntry(
    "lutein_zeaxanthin", "Lutein+Zeaxanthin", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.002,
    notes="AREDS2. Eye health. Bundled.",
))
_add(CatalogEntry(
    "astaxanthin_12", "Astaxanthin 12mg", "supplement_current",
    hr_observed=0.95, log_sd=0.12, conf_alpha=1.0, conf_beta=5.0,
    annual_cost=0, qol_annual=0.002,
    notes="CRP/HDL RCTs. Bundled.",
))
_add(CatalogEntry(
    "lycopene_15", "Lycopene 15mg", "supplement_current",
    hr_observed=0.95, log_sd=0.15, conf_alpha=1.2, conf_beta=4.8,
    annual_cost=0, qol_annual=0.000,
    notes="Song meta obs. Bundled.",
))
_add(CatalogEntry(
    "nr_300", "NR 300mg", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=0, qol_annual=0.001,
    notes="NAD+ precursor. Bundled.",
))
_add(CatalogEntry(
    "fisetin_100", "Fisetin 100mg", "supplement_current",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.000,
    notes="Senolytic. Animal. Bundled.",
))
_add(CatalogEntry(
    "spermidine_10", "Spermidine 10mg", "supplement_current",
    hr_observed=0.95, log_sd=0.15, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=0, qol_annual=0.000,
    notes="Madeo obs HR 0.70. Animal.",
))
_add(CatalogEntry(
    "luteolin_100", "Luteolin 100mg", "supplement_current",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.001,
    notes="Anti-inflammatory. Neuroprotective. Bundled.",
))
_add(CatalogEntry(
    "ubiquinol_50", "Ubiquinol 50mg", "supplement_current",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=0, qol_annual=0.001,
    notes="Q-SYMBIO RCT in HF. Healthy-pop extrapolation.",
))
_add(CatalogEntry(
    "boron_3", "Boron 3mg", "supplement_current",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=0, qol_annual=0.000,
    notes="Prostate/bone obs. Bundled.",
))
_add(CatalogEntry(
    "lithium_1mg_orotate", "Lithium 1mg orotate", "supplement_current",
    hr_observed=0.98, log_sd=0.10, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=0, qol_annual=0.001,
    notes="Ecological Li data. Neuroprotective. Bundled.",
))
_add(CatalogEntry(
    "broccoli_seed_200", "Broccoli Seed Ext 200mg", "supplement_current",
    hr_observed=0.95, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=0, qol_annual=0.000,
    notes="Sulforaphane. Phase 2 enzyme induction. Bundled.",
))
_add(CatalogEntry(
    "cocoa_flavanols_500", "Cocoa flavanols ~500mg", "supplement_current",
    hr_observed=0.90, log_sd=0.12, conf_alpha=2.5, conf_beta=3.0,
    annual_cost=0, qol_annual=0.001,
    notes="COSMOS RCT HR 0.73 CVD. Free via cocoa powder.",
))
_add(CatalogEntry(
    "hyaluronic_acid_120", "Hyaluronic acid (oral)", "supplement_current",
    hr_observed=0.99, log_sd=0.08, conf_alpha=1.0, conf_beta=7.0,
    annual_cost=0, qol_annual=0.001,
    notes="Already 120mg in Longevity Mix. Joint/skin. No mortality.",
))

# ---------------------------------------------------------------------------
# Supplements — already purchased (new additions)
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "glycine_2g", "Glycine 2g bedtime", "supplement_bought",
    hr_observed=0.965, log_sd=0.12, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=28,  # $17.40 / 227 doses (1lb/151×3g servings, 2g dose) * 365
    qol_annual=0.006,
    notes="Mouse lifespan +5%. Sleep RCTs.",
    sources=["https://www.amazon.com/dp/B0013OVZJW"],
))
_add(CatalogEntry(
    "apigenin_50", "Apigenin 50mg", "supplement_bought",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=76,  # $24.95 / 120 caps * 365
    qol_annual=0.005,
    notes="CD38 inhibitor. Anxiolytic.",
    sources=["https://www.amazon.com/dp/B09DGTBBSF"],
))
_add(CatalogEntry(
    "omega3_epa_2g", "High-EPA Omega-3 +2g", "supplement_bought",
    hr_observed=0.955, log_sd=0.10, conf_alpha=2.5, conf_beta=3.0,
    annual_cost=227,  # $27.95 / 90 softgels * 2/day = 45 days, * 365/45
    qol_annual=0.002,
    notes="Incremental over CLO. VITAL/REDUCE-IT.",
    sources=["https://www.amazon.com/dp/B07DX89ZHN"],
))
_add(CatalogEntry(
    "taurine_500_topup", "Taurine 500mg top-up", "supplement_bought",
    hr_observed=0.985, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=4,  # $23.97 / 2000 doses (1kg, 500mg dose) * 365
    qol_annual=0.001,
    notes="Incremental over 1500mg in Longevity Mix.",
    sources=["https://www.amazon.com/dp/B00ENSLW7A"],
))

# ---------------------------------------------------------------------------
# Supplements — candidates
# ---------------------------------------------------------------------------
_add(CatalogEntry(
    "urolithin_a_500", "Urolithin A 500mg", "supplement_candidate",
    hr_observed=0.94, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=780, qol_annual=0.003,
    notes="Mitopure. RCTs: improved mitochondrial function. Expensive.",
))
_add(CatalogEntry(
    "ergothioneine_5", "Ergothioneine 5mg", "supplement_candidate",
    hr_observed=0.94, log_sd=0.15, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=240, qol_annual=0.001,
    notes="Longevity vitamin hypothesis. Obs: low ergo → higher mortality.",
))
_add(CatalogEntry(
    "quercetin_500", "Quercetin 500mg", "supplement_candidate",
    hr_observed=0.93, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.000,
    notes="Senolytic. Anti-inflammatory. Animal lifespan.",
))
_add(CatalogEntry(
    "sulforaphane_20_extra", "Sulforaphane 20mg (extra)", "supplement_candidate",
    hr_observed=0.94, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=180, qol_annual=0.000,
    notes="NRF2 activator. Incremental over Broccoli Seed Ext.",
))
_add(CatalogEntry(
    "pterostilbene_50", "Pterostilbene 50mg", "supplement_candidate",
    hr_observed=0.96, log_sd=0.15, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=120, qol_annual=0.000,
    notes="Resveratrol analog. AMPK/SIRT1. Animal only.",
))
_add(CatalogEntry(
    "egcg_400", "EGCG 400mg (green tea)", "supplement_candidate",
    hr_observed=0.92, log_sd=0.15, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.000,
    notes="Obs meta HR 0.74-0.85. Heavily confounded. Liver risk at high dose.",
))
_add(CatalogEntry(
    "berberine_500", "Berberine 500mg", "supplement_candidate",
    hr_observed=0.88, log_sd=0.18, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=180, qol_annual=-0.004,
    notes="Metformin-like. RCTs in diabetes. GI side effects.",
))
_add(CatalogEntry(
    "alpha_lipoic_acid_300", "Alpha-lipoic acid 300mg", "supplement_candidate",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=60, qol_annual=0.000,
    notes="Antioxidant. RCTs for diabetic neuropathy.",
))
_add(CatalogEntry(
    "pqq_20", "PQQ 20mg", "supplement_candidate",
    hr_observed=0.97, log_sd=0.12, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=180, qol_annual=0.001,
    notes="Mitochondrial biogenesis. Small RCTs. Expensive.",
))
_add(CatalogEntry(
    "tmg_1g", "TMG/Betaine 1g", "supplement_candidate",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.0, conf_beta=5.5,
    annual_cost=30, qol_annual=0.000,
    notes="Methyl donor. Homocysteine reduction. Often paired with NR/NMN.",
))
_add(CatalogEntry(
    "ashwagandha_600", "Ashwagandha 600mg", "supplement_candidate",
    hr_observed=0.96, log_sd=0.15, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=60, qol_annual=0.008,
    notes="RCTs: cortisol, anxiety, sleep, testosterone. Rare liver concern.",
))
_add(CatalogEntry(
    "lions_mane_1g", "Lions Mane 1g", "supplement_bought",
    hr_observed=0.98, log_sd=0.12, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=287,  # $47.21 / 120 caps, 2/day = 60 days, * 365/60
    qol_annual=0.003,
    notes="NGF stimulation. Small RCTs: cognitive improvement.",
    sources=["https://www.amazon.com/dp/B00OVF9DVM"],
))
_add(CatalogEntry(
    "black_seed_oil_1g", "Black seed oil 1g", "supplement_candidate",
    hr_observed=0.91, log_sd=0.18, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=60, qol_annual=0.000,
    notes="Thymoquinone. Anti-inflammatory. No mortality RCTs.",
))
_add(CatalogEntry(
    "cistanche_200", "Cistanche 200mg", "supplement_bought",
    hr_observed=0.95, log_sd=0.18, conf_alpha=1.0, conf_beta=6.0,
    annual_cost=231,  # $37.99 / 60 tabs, 1/day = 60 days, * 365/60
    qol_annual=0.002,
    notes="Testosterone, anti-aging TCM. Very limited human data.",
    sources=["https://www.amazon.com/dp/B08VTFXWQF"],
))
_add(CatalogEntry(
    "nmn_500", "NMN 500mg", "supplement_candidate",
    hr_observed=0.96, log_sd=0.12, conf_alpha=1.2, conf_beta=5.0,
    annual_cost=360, qol_annual=0.001,
    notes="NAD+ precursor (alt to NR). Already getting NR 300mg. Expensive.",
))
_add(CatalogEntry(
    "ghk_cu", "GHK-Cu peptide (topical)", "supplement_candidate",
    hr_observed=0.99, log_sd=0.10, conf_alpha=1.0, conf_beta=7.0,
    annual_cost=300, qol_annual=0.002,
    notes="Wound healing, collagen. Skin only.",
))
_add(CatalogEntry(
    "vitamin_c_500_extra", "Vitamin C 500mg (extra)", "supplement_candidate",
    hr_observed=0.97, log_sd=0.08, conf_alpha=2.0, conf_beta=4.5,
    annual_cost=15, qol_annual=0.000,
    notes="Already getting 250mg from Longevity Mix. Obs meta: modest CVD.",
))
_add(CatalogEntry(
    "zinc_carnosine_75", "Zinc carnosine 75mg", "supplement_candidate",
    hr_observed=0.97, log_sd=0.10, conf_alpha=1.5, conf_beta=4.5,
    annual_cost=60, qol_annual=0.001,
    notes="Gut barrier integrity. Already getting zinc 15mg.",
))


def get_catalog(
    categories: Optional[List[str]] = None,
) -> Dict[str, CatalogEntry]:
    """Get catalog entries, optionally filtered by category."""
    if categories is None:
        return dict(CATALOG)
    return {k: v for k, v in CATALOG.items() if v.category in categories}


def simulate_catalog(
    profile,
    n_simulations: int = 50_000,
    random_state: int = 42,
    pub_bias_shrinkage: float = 0.30,
    horizon_years: float = 40,
    qaly_discount_rate: float = 0.0,
    cost_discount_rate: float = 0.05,
    wtp: float = 200_000,
    categories: Optional[List[str]] = None,
) -> List[Dict]:
    """
    Simulate all catalog entries and return sorted results.

    Returns list of dicts with: id, name, category, hr_observed, hr_corrected,
    total_qaly, days, p_benefit, annual_cost, gross_value, cost_per_qaly.

    Costs are survival-weighted and discounted at cost_discount_rate (default 5%,
    reflecting opportunity cost of investing in equities). QALYs are undiscounted
    by default (a year of life at 80 is as valuable as at 40).
    """
    from .simulate import simulate_qaly_profile_vectorized

    entries = get_catalog(categories)
    results = []

    for entry in entries.values():
        intervention = entry.to_intervention(pub_bias_shrinkage)
        r = simulate_qaly_profile_vectorized(
            intervention, profile,
            n_simulations=n_simulations,
            discount_rate=qaly_discount_rate,
            cost_discount_rate=cost_discount_rate,
            random_state=random_state,
        )
        hr_corrected = publication_bias_correct(entry.hr_observed, pub_bias_shrinkage)
        mort_qaly = r.mean
        qol_qaly = entry.qol_annual * horizon_years
        total_qaly = mort_qaly + qol_qaly
        # Survival-weighted discounted cost
        total_cost = entry.annual_cost * r.expected_discounted_cost_factor
        cost_per_qaly = total_cost / total_qaly if total_qaly > 0 and entry.annual_cost > 0 else None

        results.append({
            "id": entry.id,
            "name": entry.name,
            "category": entry.category,
            "hr_observed": entry.hr_observed,
            "hr_corrected": hr_corrected,
            "mort_qaly": mort_qaly,
            "qol_qaly": qol_qaly,
            "total_qaly": total_qaly,
            "days": total_qaly * 365.25,
            "p_benefit": r.prob_positive,
            "annual_cost": entry.annual_cost,
            "total_cost": total_cost,
            "cost_per_qaly": cost_per_qaly,
            "expected_discounted_cost_factor": r.expected_discounted_cost_factor,
            "gross_value": total_qaly * wtp - total_cost,
        })

    results.sort(key=lambda x: x["gross_value"], reverse=True)
    return results
