"""Per-item evidence annotations for QoL and sleep-relief claims.

Single source of truth consumed by BOTH pipelines (the catalog/analyzer path
behind protocol-data.json and the personalized ground-up path), so the two can
never drift on how a claim's evidence is graded.

Conventions:

- **Positive claims only.** Authored *negative* qol_annual values (e.g. the
  lean-user GLP-1 penalty) are deliberately left unguarded: shrinking a
  claimed harm would flatter the intervention, and the repo's convention is
  that conservatism cuts against the intervention on both sides (direct
  harm_effects are not evidence-shrunk either).
- **General-QoL claims default to ``authored_shaded``**: the authored means
  already embed a private severity judgment, so they take study-quality
  shrinkage plus a residual-optimism prior only. Re-anchoring one to a
  published placebo-adjusted delta (``published_delta``) is a per-item
  decision that needs the user's severity input.
- **Sleep-relief fractions use ``published_delta``**: personal severity is
  measured upstream (wearables + home sleep study), so the relief fraction is
  a pure evidence claim and takes the full category transport prior.
"""

from __future__ import annotations

from typing import Dict, Optional

from .provisional_params import (
    L_THEANINE_BEDTIME_ID,
    L_THEANINE_BEDTIME_QOL_CATEGORY,
    L_THEANINE_BEDTIME_QOL_STUDY_QUALITY,
)
from .qol_evidence import QolEvidence
from .sleep_residual import ResidualMode, apply_sleep_residual_rule

# --------------------------------------------------------------------------
# General QoL (qol_annual) claims — anchor: authored_shaded unless noted.
# --------------------------------------------------------------------------
GENERAL_QOL_EVIDENCE: Dict[str, QolEvidence] = {
    "tadalafil_2.5mg": QolEvidence(
        "rct_placebo_patient_reported",
        "sexual_function",
        note="Large placebo-adjusted IIEF deltas in pivotal PDE5 RCTs; authored mean already shades the Stolk TTO gain for severity.",
        sources=("Goldstein 1998",),
    ),
    "trazodone_50mg": QolEvidence(
        "rct_placebo_patient_reported",
        "sleep_symptom",
        note="Short placebo-controlled insomnia trials with modest subjective gains; no long-term efficacy RCTs at hypnotic doses.",
        sources=("Yi 2018 meta-analysis",),
    ),
    "finasteride_1.25mg": QolEvidence(
        "rct_objective_endpoint",
        "hair_skin",
        note="Objective photographic hair-count RCTs; utility mapping leans on an alopecia TTO proxy.",
        sources=("Kaufman 1998",),
    ),
    "hiit_1x_week": QolEvidence(
        "rct_objective_endpoint",
        "fitness_function",
        note="CRF gains are objective and meta-analytic; shrink covers the CRF-to-utility mapping.",
        sources=("Milanovic 2015",),
    ),
    "hiit_2x_week": QolEvidence(
        "rct_objective_endpoint",
        "fitness_function",
        note="As hiit_1x_week.",
        sources=("Milanovic 2015",),
    ),
    "hiit_3x_week": QolEvidence(
        "rct_objective_endpoint",
        "fitness_function",
        note="As hiit_1x_week; marginal dose already discounted by hiit_headroom.",
        sources=("Milanovic 2015",),
    ),
    "tempo_run_1x_week": QolEvidence(
        "rct_objective_endpoint",
        "fitness_function",
        note="Threshold-training CRF evidence, intermediate intensity.",
        sources=("Milanovic 2015",),
    ),
    "zone2_cardio_2x_week": QolEvidence(
        "rct_objective_endpoint",
        "fitness_function",
        note="Moderate-intensity CRF evidence.",
    ),
    "strength_maintenance": QolEvidence(
        "rct_objective_endpoint",
        "fitness_function",
        note="Strength gains objective; kept near-flat by authoring because daily lifting already happens.",
    ),
    "magnesium_200": QolEvidence(
        "supplement_industry_rct",
        "sleep_symptom",
        note="Small, high-bias sleep trials; systematic review grades certainty low-to-very-low.",
        sources=("Mah & Pitre 2021",),
    ),
    "melatonin_300mcg": QolEvidence(
        "meta_analysis_placebo_rcts",
        "sleep_symptom",
        note="Meta-analytic but objectively tiny effects (latency ~-7 min); low-dose protocol.",
        sources=("Ferracioli-Oda 2013",),
    ),
    "lemborexant_5mg": QolEvidence(
        "rct_placebo_patient_reported",
        "sleep_symptom",
        note="Registered pharma RCTs with PSG support; QoL claim is daytime function.",
        sources=("SUNRISE trials",),
    ),
    "daridorexant_25mg": QolEvidence(
        "rct_placebo_patient_reported",
        "sleep_symptom",
        note="Registered RCTs including a daytime-functioning instrument (IDSIQ).",
    ),
    "suvorexant_10mg": QolEvidence(
        "rct_placebo_patient_reported",
        "sleep_symptom",
        note="Registered RCTs; subjective daytime benefit modest.",
    ),
    "doxepin_3mg": QolEvidence(
        "rct_placebo_patient_reported",
        "sleep_symptom",
        note="Low-dose doxepin RCTs with objective WASO endpoints.",
    ),
    "prebiotics": QolEvidence(
        "supplement_industry_rct",
        "gi_symptom",
        note="Fiber/prebiotic trials are small with subjective GI endpoints.",
    ),
    "probiotic_daily": QolEvidence(
        "supplement_industry_rct",
        "gi_symptom",
        note="Strain-specific effects transport poorly across products.",
        sources=("Ford 2018",),
    ),
    "zinc_carnosine_75": QolEvidence(
        "supplement_industry_rct",
        "gi_symptom",
        note="Small manufacturer-adjacent gut-lining trials.",
    ),
    "ginger_400": QolEvidence(
        "supplement_industry_rct",
        "gi_symptom",
        note="Real nausea RCTs exist, but the claim here is diffuse GI/anti-inflammatory support.",
    ),
    "ashwagandha_600": QolEvidence(
        "supplement_industry_rct",
        "mood_stress",
        note="Commercial trials small and unregistered; effects shrink in better designs.",
        sources=("Speers 2021",),
    ),
    "l_theanine_200": QolEvidence(
        "supplement_industry_rct",
        "mood_stress",
        note="Small acute-stress trials, subjective endpoints.",
    ),
    L_THEANINE_BEDTIME_ID: QolEvidence(
        L_THEANINE_BEDTIME_QOL_STUDY_QUALITY,
        L_THEANINE_BEDTIME_QOL_CATEGORY,
        note="PROVISIONAL tier (glycine_2g's) pending evidence adjudication; see provisional_params.py.",
    ),
    "lithium_5mg": QolEvidence(
        "observational_symptom",
        "mood_stress",
        note="Low-dose mood claim rides on ecological/observational signals only.",
    ),
    "creatine_5g": QolEvidence(
        "rct_placebo_patient_reported",
        "cognitive",
        note="Strength effects are robust; the authored claim is mostly cognitive-resilience, where meta-analytic effects are small and domain-specific.",
        sources=("Avgerinos 2018",),
    ),
    "lions_mane_1g": QolEvidence(
        "supplement_industry_rct",
        "cognitive",
        note="Tiny pilot trials; healthy-adult cognition evidence weakest tier of RCT.",
        sources=("Docherty 2023",),
    ),
    "apigenin_50": QolEvidence(
        "mechanistic_or_self_experiment",
        "sleep_symptom",
        note="Mechanistic (GABA-adjacent) rationale; no human sleep RCTs at this dose.",
    ),
    "glycine_2g": QolEvidence(
        "supplement_industry_rct",
        "sleep_symptom",
        note="Small manufacturer-affiliated sleep-quality trials.",
    ),
    "nac_1200": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        note="Placebo-controlled mucolytic RCTs in chronic airway disease; upper-airway sleep transport far weaker.",
    ),
    "nr_300": QolEvidence(
        "supplement_industry_rct",
        "general_vitality",
        note="NAD-precursor trials raise biomarkers, not validated wellbeing endpoints.",
    ),
    "nr_300_unbundled": QolEvidence(
        "supplement_industry_rct",
        "general_vitality",
        note="As nr_300.",
    ),
    "urolithin_a_500": QolEvidence(
        "supplement_industry_rct",
        "fitness_function",
        note="Manufacturer RCTs report small muscle-endurance gains.",
    ),
    "quercetin_500": QolEvidence(
        "mechanistic_or_self_experiment",
        "general_vitality",
        note="Senolytic rationale is mechanistic; human functional endpoints absent.",
    ),
    "collagen_22g": QolEvidence(
        "supplement_industry_rct",
        "hair_skin",
        note="Industry skin-elasticity trials; joint claims weaker still.",
    ),
    "hyaluronic_acid_120": QolEvidence(
        "supplement_industry_rct",
        "hair_skin",
        note="Oral HA skin-hydration trials are small and industry-run.",
    ),
    "curcumin_250": QolEvidence(
        "supplement_industry_rct",
        "pain_joint",
        note="Joint/inflammation trials with large placebo responses; bioavailability varies by formulation.",
    ),
    "cistanche_200": QolEvidence(
        "mechanistic_or_self_experiment",
        "general_vitality",
        note="Largely animal/mechanistic literature.",
    ),
    "traditional_sauna_4x_week": QolEvidence(
        "observational_symptom",
        "general_vitality",
        note="KIHD association plus small relaxation trials; wellbeing claim subjective.",
    ),
    "infrared_sauna_4x_week": QolEvidence(
        "observational_symptom",
        "general_vitality",
        note="Weaker evidence base than traditional sauna.",
    ),
    "nasacort_nightly": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        note="Robust allergic-rhinitis RCT base; sleep-specific benefit more modest.",
        sources=("Kiely 2004",),
    ),
    "nasal_strips_nightly": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        note="Placebo-controlled congestion trials show modest objective effects.",
    ),
    "head_elevation_nightly": QolEvidence(
        "mechanistic_or_self_experiment",
        "respiratory_airway",
        note="Positional rationale with small uncontrolled studies.",
    ),
    "mouth_tape_nightly": QolEvidence(
        "mechanistic_or_self_experiment",
        "respiratory_airway",
        note="Mechanistic nasal-route rationale; near-absent trial evidence.",
    ),
    "humidifier_nightly": QolEvidence(
        "mechanistic_or_self_experiment",
        "respiratory_airway",
        note="Comfort rationale; no controlled sleep trials.",
    ),
    "apap_nightly": QolEvidence(
        "rct_objective_endpoint",
        "respiratory_airway",
        note="Sham-controlled CPAP trials plus objective AHI normalization.",
        sources=("Jenkinson 1999",),
    ),
    "oral_appliance_custom": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        note="MAD RCTs against sham devices; smaller objective effect than CPAP.",
    ),
    "lutein_zeaxanthin": QolEvidence(
        "rct_objective_endpoint",
        "general_vitality",
        note="AREDS2 is objective for progression in AMD patients; healthy-eye visual-function claim is a far transport.",
        sources=("AREDS2 2013",),
    ),
    # ---- Catalog-level candidates and bundle constituents (positive claims
    # that appear in the public catalog even when the personal spec overrides
    # them, e.g. semaglutide is a net-negative for a lean user). ----
    "semaglutide": QolEvidence(
        "rct_placebo_patient_reported",
        "metabolic_symptom",
        note="STEP/SELECT RCTs are strong for weight and events; the catalog QoL claim maps weight loss to wellbeing.",
        sources=("SELECT 2023",),
    ),
    "empagliflozin": QolEvidence(
        "rct_placebo_patient_reported",
        "metabolic_symptom",
        note="Registered cardiometabolic RCTs; QoL claim indirect for a normoglycemic user.",
    ),
    "astaxanthin_12": QolEvidence(
        "supplement_industry_rct",
        "general_vitality",
        note="Small industry trials on skin/fatigue endpoints.",
    ),
    "omega3_epa_2g": QolEvidence(
        "rct_placebo_patient_reported",
        "mood_stress",
        note="High-EPA mood RCTs exist in depressed populations; transport to euthymic users is far.",
    ),
    "omega3_clo": QolEvidence(
        "rct_placebo_patient_reported",
        "general_vitality",
        note="Omega-3 RCT base broad; wellbeing claim diffuse at replete status.",
    ),
    "ghk_cu": QolEvidence(
        "mechanistic_or_self_experiment",
        "hair_skin",
        note="Peptide cosmetic claims; no registered trials.",
    ),
    "luteolin_100": QolEvidence(
        "mechanistic_or_self_experiment",
        "general_vitality",
        note="Mechanistic senolytic/anti-inflammatory rationale only.",
    ),
    "luteolin_100_unbundled": QolEvidence(
        "mechanistic_or_self_experiment",
        "general_vitality",
        note="As luteolin_100.",
    ),
    "ubiquinol_50": QolEvidence(
        "supplement_industry_rct",
        "general_vitality",
        note="CoQ10 fatigue trials small; statin-myalgia context does not apply.",
    ),
    "ubiquinol_50_unbundled": QolEvidence(
        "supplement_industry_rct",
        "general_vitality",
        note="As ubiquinol_50.",
    ),
    "lithium_1mg_orotate": QolEvidence(
        "observational_symptom",
        "mood_stress",
        note="Trace-dose mood claim rides on ecological associations.",
    ),
    "cocoa_flavanols_500": QolEvidence(
        "rct_placebo_patient_reported",
        "cognitive",
        note="COSMOS-Mind cognition signal exists but is contested and modest.",
        sources=("COSMOS-Mind 2022",),
    ),
    "ergothioneine_5": QolEvidence(
        "observational_symptom",
        "general_vitality",
        note="Observational longevity-marker associations only.",
    ),
    "pqq_20": QolEvidence(
        "supplement_industry_rct",
        "general_vitality",
        note="Tiny industry fatigue/sleep trials.",
    ),
    "nmn_500": QolEvidence(
        "supplement_industry_rct",
        "general_vitality",
        note="NAD-precursor trials raise biomarkers, not validated wellbeing endpoints.",
    ),
    "hbot_60sessions": QolEvidence(
        "rct_open_label",
        "general_vitality",
        note="HBOT longevity protocols rest on small open-label or poorly blinded studies.",
    ),
    "taurine_500_topup": QolEvidence(
        "observational_symptom",
        "general_vitality",
        note="Cross-species longevity signal; human wellbeing claim diffuse.",
    ),
    "bpc157_cycle": QolEvidence(
        "mechanistic_or_self_experiment",
        "pain_joint",
        note="Animal-only evidence; no human RCTs.",
    ),
    "tb500_cycle": QolEvidence(
        "mechanistic_or_self_experiment",
        "pain_joint",
        note="Animal-only evidence; no human RCTs.",
    ),
}

# --------------------------------------------------------------------------
# Sleep-relief fraction claims — anchor: published_delta (severity measured).
# --------------------------------------------------------------------------
_SLEEP = "published_delta"
SLEEP_RELIEF_EVIDENCE: Dict[str, QolEvidence] = {
    "apap_nightly": QolEvidence(
        "rct_objective_endpoint",
        "respiratory_airway",
        _SLEEP,
        note="Objective AHI control; sham-controlled subjective gains.",
        sources=("Jenkinson 1999",),
    ),
    "oral_appliance_custom": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        _SLEEP,
        note="Sham-controlled MAD trials.",
    ),
    "nasacort_nightly": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        _SLEEP,
        note="Placebo-controlled nasal steroid trials in snorers/rhinitis.",
        sources=("Kiely 2004",),
    ),
    "nasal_strips_nightly": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        _SLEEP,
        note="Placebo-controlled, small objective effects.",
    ),
    "mouth_tape_nightly": QolEvidence(
        "mechanistic_or_self_experiment",
        "respiratory_airway",
        _SLEEP,
        note="Mechanistic only.",
    ),
    "head_elevation_nightly": QolEvidence(
        "mechanistic_or_self_experiment",
        "respiratory_airway",
        _SLEEP,
        note="Small uncontrolled positional studies.",
    ),
    "humidifier_nightly": QolEvidence(
        "mechanistic_or_self_experiment",
        "respiratory_airway",
        _SLEEP,
        note="Comfort rationale only.",
    ),
    "nac_1200": QolEvidence(
        "rct_placebo_patient_reported",
        "respiratory_airway",
        _SLEEP,
        note="Mucolytic RCTs in lower-airway disease; sleep transport weak.",
    ),
    "trazodone_50mg": QolEvidence(
        "rct_placebo_patient_reported",
        "sleep_symptom",
        _SLEEP,
        note="Short placebo-controlled trials; subjective endpoints.",
        sources=("Yi 2018 meta-analysis",),
    ),
    "magnesium_200": QolEvidence(
        "supplement_industry_rct",
        "sleep_symptom",
        _SLEEP,
        note="Low-certainty small trials.",
        sources=("Mah & Pitre 2021",),
    ),
    "melatonin_300mcg": QolEvidence(
        "meta_analysis_placebo_rcts",
        "sleep_symptom",
        _SLEEP,
        note="Meta-analytic; objectively small.",
        sources=("Ferracioli-Oda 2013",),
    ),
    "ashwagandha_600": QolEvidence(
        "supplement_industry_rct",
        "sleep_symptom",
        _SLEEP,
        note="Commercial sleep-quality trials.",
        sources=("Speers 2021",),
    ),
    "glycine_2g": QolEvidence(
        "supplement_industry_rct",
        "sleep_symptom",
        _SLEEP,
        note="Manufacturer-affiliated trials.",
    ),
    L_THEANINE_BEDTIME_ID: QolEvidence(
        L_THEANINE_BEDTIME_QOL_STUDY_QUALITY,
        L_THEANINE_BEDTIME_QOL_CATEGORY,
        _SLEEP,
        note="PROVISIONAL tier (glycine_2g's) pending evidence adjudication; see provisional_params.py.",
    ),
    "apigenin_50": QolEvidence(
        "mechanistic_or_self_experiment",
        "sleep_symptom",
        _SLEEP,
        note="No human sleep RCTs at supplement doses.",
    ),
    "lemborexant_5mg": QolEvidence(
        "rct_objective_endpoint",
        "sleep_symptom",
        _SLEEP,
        note="PSG-verified sleep-architecture endpoints.",
        sources=("SUNRISE trials",),
    ),
    "daridorexant_25mg": QolEvidence(
        "rct_objective_endpoint",
        "sleep_symptom",
        _SLEEP,
        note="PSG-verified endpoints.",
    ),
    "suvorexant_10mg": QolEvidence(
        "rct_objective_endpoint",
        "sleep_symptom",
        _SLEEP,
        note="PSG-verified endpoints.",
    ),
    "doxepin_3mg": QolEvidence(
        "rct_objective_endpoint",
        "sleep_symptom",
        _SLEEP,
        note="PSG WASO endpoints in registered trials.",
    ),
}


def general_qol_evidence_for(
    item_id: str,
    *,
    residual_mode: ResidualMode = "evidence_rule",
    sleep_component_relief: dict[str, float] | None = None,
) -> Optional[QolEvidence]:
    """Return evidence for general QoL retained by the selected residual rule.

    The default omits duplicate sleep-only claims. Historical annotations
    remain available explicitly through ``residual_mode="authored"``.
    """
    if (
        apply_sleep_residual_rule(
            item_id, 1.0, residual_mode, sleep_component_relief=sleep_component_relief
        )
        == 0
    ):
        return None
    return GENERAL_QOL_EVIDENCE.get(item_id)


def sleep_relief_evidence_for(item_id: str) -> Optional[QolEvidence]:
    return SLEEP_RELIEF_EVIDENCE.get(item_id)
