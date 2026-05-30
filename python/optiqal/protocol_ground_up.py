"""Personalized protocol assumptions and ground-up analysis for Max.

This is the canonical implementation backing the protocol exports. Site scripts
should call into this module rather than owning parallel model logic.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from .catalog import CATALOG, CatalogEntry, public_display_category
from .confounding import ConfoundingPrior
from .intervention import (
    Distribution,
    Intervention,
    MortalityEffect,
    allocate_interaction_rule,
)
from .profile import Profile
from .reference_case import (
    DEFAULT_REFERENCE_CASE,
    get_public_health_utility_weight,
    utility_reference_case_status,
)
from .simulate import simulate_qaly_profile_vectorized
from .sleep import (
    AirwayContributorEstimate,
    SleepBurdenEstimate,
    SleepMetrics,
    SleepStudyResult,
    apply_sleep_study,
    effective_sleep_component_relief,
    estimate_airway_response_signal,
    estimate_sleep_burden,
    estimate_sleep_relief_annual_qaly,
    sleep_baseline_mortality_multiplier,
    sleep_intervention_mortality_hr_multiplier,
    sleep_utility_lineage,
)
from .stack_interactions import expected_stack_interaction_qaly

N_SIMULATIONS = 40_000
SEED = 42
QALY_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.health_discount_rate
COST_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.cost_discount_rate
ACTIONABLE_STATUSES = {"considering", "testing", "watching"}
CURRENT_STACK_STATUSES = {"taking", "testing"}
REFERENCE_CASE_SENSITIVITY_RATES = (0.0, 0.015, 0.03, 0.05)
SEXUAL_FUNCTION_QOL = ("erectile_dysfunction_tto_utility_gain_stolk_2000",)
HAIR_QOL = ("mild_alopecia_areata_tto_proxy_2024",)
STRESS_QOL = ("anxiety_disorders_mild_disability_weight_europe_2015",)
SLEEP_RESIDUAL_QOL = (
    "insomnia_disability_weight_europe_2015",
    "anxiety_disorders_mild_disability_weight_europe_2015",
)
AIRWAY_SLEEP_QOL = (
    "sleep_apnoea_disability_weight_europe_2015",
    "insomnia_disability_weight_europe_2015",
)
GUT_QOL = ("irritable_bowel_syndrome_disability_weight_europe_2015",)
BOWEL_HABIT_QOL = (
    "constipation_disability_weight_europe_2015",
    "irritable_bowel_syndrome_disability_weight_europe_2015",
)
UPPER_GI_QOL = ("gerd_disability_weight_europe_2015",)
JOINT_QOL = ("low_back_pain_mild_disability_weight_europe_2015",)
VISION_QOL = ("distance_vision_mild_impairment_disability_weight_europe_2015",)
FUNCTION_QOL = ("motor_impairment_mild_disability_weight_europe_2015",)
WEIGHT_RELATED_FUNCTION_QOL = FUNCTION_QOL + SLEEP_RESIDUAL_QOL
ACUTE_MILD_QOL = (
    "infectious_disease_acute_episode_mild_disability_weight_europe_2015",
)
ACUTE_MODERATE_QOL = (
    "infectious_disease_acute_episode_moderate_disability_weight_europe_2015",
)
ACUTE_SEVERE_QOL = (
    "infectious_disease_acute_episode_severe_disability_weight_europe_2015",
)
HARM_UTILITY_WEIGHT_IDS: dict[str, tuple[str, ...]] = {
    "sexual_or_mood_side_effects": SEXUAL_FUNCTION_QOL + STRESS_QOL,
    "sedation_stack": FUNCTION_QOL,
    "bleeding_stack": ACUTE_SEVERE_QOL,
    "duplicate_vitamin_d": ACUTE_MILD_QOL,
    "headache_or_hypotension": ACUTE_MILD_QOL + FUNCTION_QOL,
    "daytime_sedation": FUNCTION_QOL,
    "residual_sedation": FUNCTION_QOL,
    "next_day_somnolence": FUNCTION_QOL,
    "antihistamine_hangover": FUNCTION_QOL,
    "sedation_or_emotional_blunting": FUNCTION_QOL + STRESS_QOL,
    "mouth_tape_irritation_or_fragmentation": ACUTE_MILD_QOL,
    "rare_liver_or_thyroid_issue": ACUTE_SEVERE_QOL,
    "rare_liver_injury": ACUTE_SEVERE_QOL,
    "liver_injury": ACUTE_SEVERE_QOL,
    "thyroid_overactivation": ACUTE_MODERATE_QOL + STRESS_QOL,
    "gi_intolerance": GUT_QOL,
    "ongoing_gi_side_effects": GUT_QOL,
    "gallbladder_or_pancreatitis": ACUTE_SEVERE_QOL,
    "bleeding": ACUTE_SEVERE_QOL,
    "barotrauma_or_oxygen_toxicity": ACUTE_MODERATE_QOL,
    "gray_market_peptide_quality_risk": ACUTE_MILD_QOL,
    "gray_market_tb500_quality_risk": ACUTE_MILD_QOL,
}
QOL_UNCERTAINTY_RELATIVE_SD_BY_EVIDENCE = {
    "high": 0.35,
    "moderate": 0.60,
    "low": 0.90,
    "very-low": 1.25,
}
DEFAULT_QOL_UNCERTAINTY_RELATIVE_SD = 0.75
LATENT_GLOBAL_SCORE_WEIGHT = 0.18
LATENT_MECHANISM_SCORE_WEIGHT = 0.32
LATENT_CATEGORY_SCORE_WEIGHT = 0.12
LATENT_MAX_SHARED_SCORE_WEIGHT = 0.55
PROTOCOL_OPTIMIZER_WTP = 200_000
PROTOCOL_OPTIMIZER_MAX_STEPS = 40
PROTOCOL_OPTIMIZER_MIN_IMPROVEMENT = 1e-6
GLP1_STEP_WEIGHT_LOSS_FRACTION = 0.124
GLP1_DURABLE_EFFECT_FRACTION = 0.65
GLP1_DIABETES_WEIGHT_LOSS_MULTIPLIER = 0.70
GLP1_ALL_CAUSE_PROXY_HR = 0.92
GLP1_SOURCES = (
    "https://pubmed.ncbi.nlm.nih.gov/37952131/",
    "https://pubmed.ncbi.nlm.nih.gov/33567185/",
    "https://pubmed.ncbi.nlm.nih.gov/35441470/",
    "https://www.ncbi.nlm.nih.gov/books/NBK601688/",
)

@dataclass(frozen=True)
class ProtocolContext:
    """Container for personalized protocol inputs and filesystem locations."""

    root: Path
    protocol_json: Path
    health_db: Path
    output_json: Path
    output_md: Path
    profile: Profile
    home_sleep_study: SleepStudyResult


DEFAULT_PROTOCOL_CONTEXT = ProtocolContext(
    root=Path.home() / "maxghenis.com",
    protocol_json=Path.home() / "maxghenis.com" / "src" / "data" / "protocol-data.json",
    health_db=Path.home() / "clawd" / "data" / "health.db",
    output_json=Path.home() / "maxghenis.com" / "src" / "data" / "protocol-ground-up.json",
    output_md=Path.home() / "maxghenis.com" / "src" / "data" / "protocol-ground-up.md",
    profile=Profile(
        age=39,
        sex="male",
        bmi_category="normal",
        smoking_status="never",
        has_diabetes=False,
        has_hypertension=False,
        activity_level="active",
    ),
    home_sleep_study=SleepStudyResult(
        study_type="home",
        rei=7.7,
        mean_spo2=97.0,
        nadir_spo2=94.0,
        total_sleep_hours=7.1,
        obstructive_apneas=35,
        hypopneas=19,
        central_apneas=0,
        mixed_apneas=0,
        supine_fraction=0.52,
        supine_rei=5.2,
        used_nasal_steroid=True,
        used_nasal_strips=True,
    ),
)

# Backward-compatible aliases while callers migrate to ProtocolContext.
ROOT = DEFAULT_PROTOCOL_CONTEXT.root
PROTOCOL_JSON = DEFAULT_PROTOCOL_CONTEXT.protocol_json
HEALTH_DB = DEFAULT_PROTOCOL_CONTEXT.health_db
OUTPUT_JSON = DEFAULT_PROTOCOL_CONTEXT.output_json
OUTPUT_MD = DEFAULT_PROTOCOL_CONTEXT.output_md
HOME_SLEEP_STUDY = DEFAULT_PROTOCOL_CONTEXT.home_sleep_study
PROFILE = DEFAULT_PROTOCOL_CONTEXT.profile


@dataclass(frozen=True)
class StackSpec:
    item_id: str
    observed_hr: float | None = None
    log_sd: float | None = None
    conf_alpha: float | None = None
    conf_beta: float | None = None
    qol_annual: float | None = None
    qol_years: float | None = None
    low_qaly: float = math.nan
    high_qaly: float = math.nan
    personalization: str | None = None
    rationale: str | None = None
    sources: tuple[str, ...] | None = None
    general_qol_utility_weight_ids: tuple[str, ...] | None = None
    general_qol_lineage_note: str | None = None
    sleep_component_relief: dict[str, float] | None = None
    airway_target_weights: dict[str, float] | None = None
    apply_profile_effect_rules: bool = True
    model_details: dict[str, Any] | None = None


@dataclass(frozen=True)
class ResolvedStackSpec:
    item_id: str
    observed_hr: float
    log_sd: float
    conf_alpha: float
    conf_beta: float
    qol_annual: float
    qol_years: float
    low_qaly: float
    high_qaly: float
    personalization: str
    rationale: str
    sources: tuple[str, ...]
    general_qol_utility_weight_ids: tuple[str, ...] = ()
    general_qol_lineage_note: str | None = None
    sleep_component_relief: dict[str, float] = field(default_factory=dict)
    airway_target_weights: dict[str, float] = field(default_factory=dict)
    apply_profile_effect_rules: bool = True
    model_details: dict[str, Any] | None = None


def resolve_protocol_context(context: ProtocolContext | None = None) -> ProtocolContext:
    """Return the provided protocol context or the default personalized context."""
    return context or DEFAULT_PROTOCOL_CONTEXT


def make_spec(
    item_id: str,
    observed_hr: float | None = None,
    log_sd: float | None = None,
    conf_alpha: float | None = None,
    conf_beta: float | None = None,
    qol_annual: float | None = None,
    qol_years: float | None = None,
    low_qaly: float = math.nan,
    high_qaly: float = math.nan,
    personalization: str | None = None,
    rationale: str | None = None,
    sources: tuple[str, ...] | None = None,
    general_qol_utility_weight_ids: tuple[str, ...] | None = None,
    general_qol_lineage_note: str | None = None,
    sleep_component_relief: dict[str, float] | None = None,
    airway_target_weights: dict[str, float] | None = None,
    apply_profile_effect_rules: bool = True,
    model_details: dict[str, Any] | None = None,
) -> StackSpec:
    return StackSpec(
        item_id=item_id,
        observed_hr=observed_hr,
        log_sd=log_sd,
        conf_alpha=conf_alpha,
        conf_beta=conf_beta,
        qol_annual=qol_annual,
        qol_years=qol_years,
        low_qaly=low_qaly,
        high_qaly=high_qaly,
        personalization=personalization,
        rationale=rationale,
        sources=None if sources is None else tuple(sources),
        general_qol_utility_weight_ids=(
            None
            if general_qol_utility_weight_ids is None
            else tuple(general_qol_utility_weight_ids)
        ),
        general_qol_lineage_note=general_qol_lineage_note,
        sleep_component_relief=None if sleep_component_relief is None else dict(sleep_component_relief),
        airway_target_weights=None if airway_target_weights is None else dict(airway_target_weights),
        apply_profile_effect_rules=apply_profile_effect_rules,
        model_details=None if model_details is None else dict(model_details),
    )


def _resolve_required_float(
    *,
    item_id: str,
    field_name: str,
    value: float | None,
    fallback: float | None,
) -> float:
    if value is not None:
        return float(value)
    if fallback is not None:
        return float(fallback)
    raise ValueError(f"StackSpec {item_id} is missing required field {field_name}")


def _resolve_required_range(
    *,
    item_id: str,
    field_name: str,
    value: float,
) -> float:
    if math.isnan(value):
        raise ValueError(f"StackSpec {item_id} is missing required field {field_name}")
    return float(value)


def resolve_stack_spec(
    spec: StackSpec,
    base_entry: CatalogEntry | None = None,
) -> ResolvedStackSpec:
    """Resolve a sparse StackSpec against the canonical catalog when available."""
    base_entry = base_entry or CATALOG.get(spec.item_id)
    fallback_notes = base_entry.notes if base_entry is not None else ""
    fallback_sources = tuple(base_entry.sources) if base_entry is not None else ()

    return ResolvedStackSpec(
        item_id=spec.item_id,
        observed_hr=_resolve_required_float(
            item_id=spec.item_id,
            field_name="observed_hr",
            value=spec.observed_hr,
            fallback=base_entry.hr_observed if base_entry is not None else None,
        ),
        log_sd=_resolve_required_float(
            item_id=spec.item_id,
            field_name="log_sd",
            value=spec.log_sd,
            fallback=base_entry.log_sd if base_entry is not None else None,
        ),
        conf_alpha=_resolve_required_float(
            item_id=spec.item_id,
            field_name="conf_alpha",
            value=spec.conf_alpha,
            fallback=base_entry.conf_alpha if base_entry is not None else None,
        ),
        conf_beta=_resolve_required_float(
            item_id=spec.item_id,
            field_name="conf_beta",
            value=spec.conf_beta,
            fallback=base_entry.conf_beta if base_entry is not None else None,
        ),
        qol_annual=_resolve_required_float(
            item_id=spec.item_id,
            field_name="qol_annual",
            value=spec.qol_annual,
            fallback=base_entry.qol_annual if base_entry is not None else None,
        ),
        qol_years=_resolve_required_float(
            item_id=spec.item_id,
            field_name="qol_years",
            value=spec.qol_years,
            fallback=base_entry.qol_years if base_entry is not None else None,
        ),
        low_qaly=_resolve_required_range(
            item_id=spec.item_id,
            field_name="low_qaly",
            value=spec.low_qaly,
        ),
        high_qaly=_resolve_required_range(
            item_id=spec.item_id,
            field_name="high_qaly",
            value=spec.high_qaly,
        ),
        personalization=fallback_notes if spec.personalization is None else spec.personalization,
        rationale=fallback_notes if spec.rationale is None else spec.rationale,
        sources=fallback_sources if spec.sources is None else tuple(spec.sources),
        general_qol_utility_weight_ids=(
            ()
            if spec.general_qol_utility_weight_ids is None
            else tuple(spec.general_qol_utility_weight_ids)
        ),
        general_qol_lineage_note=spec.general_qol_lineage_note,
        sleep_component_relief=(
            dict(spec.sleep_component_relief)
            if spec.sleep_component_relief is not None
            else dict(base_entry.sleep_component_relief if base_entry is not None else {})
        ),
        airway_target_weights=(
            dict(spec.airway_target_weights)
            if spec.airway_target_weights is not None
            else dict(base_entry.airway_target_weights if base_entry is not None else {})
        ),
        apply_profile_effect_rules=spec.apply_profile_effect_rules,
        model_details=None if spec.model_details is None else dict(spec.model_details),
    )


def apply_spec_to_catalog_entry(
    base_entry: CatalogEntry,
    spec: StackSpec,
    *,
    annual_cost: float | None = None,
) -> CatalogEntry:
    """Apply a protocol overlay spec onto a canonical catalog entry."""
    resolved = resolve_stack_spec(spec, base_entry)
    return replace(
        base_entry,
        hr_observed=resolved.observed_hr,
        log_sd=resolved.log_sd,
        conf_alpha=resolved.conf_alpha,
        conf_beta=resolved.conf_beta,
        annual_cost=float(base_entry.annual_cost if annual_cost is None else annual_cost),
        qol_annual=resolved.qol_annual,
        qol_years=resolved.qol_years,
        has_direct_mortality_effect=(
            base_entry.has_direct_mortality_effect
            and not math.isclose(resolved.observed_hr, 1.0, rel_tol=0.0, abs_tol=1e-12)
        ),
        profile_effect_rules=[],
        notes=resolved.rationale or base_entry.notes,
        sources=list(resolved.sources or base_entry.sources),
    )


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def latest_lab_value(
    baseline: dict[str, Any],
    marker: str,
    default: float | None = None,
) -> float | None:
    parsed = _float_or_none(baseline.get("labs", {}).get(marker))
    return default if parsed is None else parsed


def glp1_obesity_qol_disutility(bmi_category: str) -> float:
    """Annual function/QOL decrement available to recover through weight loss."""
    return {
        "normal": 0.0,
        "overweight": 0.006,
        "obese": 0.025,
        "severely_obese": 0.050,
    }.get(bmi_category, 0.0)


def glp1_weight_loss_fraction(
    profile: Profile,
    *,
    cardiometabolic_signal: float,
) -> float:
    """Durable placebo-subtracted weight-loss fraction for a phenotype.

    STEP trials show about 12.4 percentage points placebo-subtracted loss at
    68 weeks in obesity/overweight trial populations. This converts that to a
    long-horizon expected fraction after persistence, discontinuation, and
    regain, and zeroes intentional weight loss for normal-BMI profiles.
    """
    if profile.bmi_category == "normal":
        return 0.0
    if profile.bmi_category == "overweight":
        raw = GLP1_STEP_WEIGHT_LOSS_FRACTION * (
            0.45 + 0.35 * cardiometabolic_signal
        )
    elif profile.bmi_category == "obese":
        raw = GLP1_STEP_WEIGHT_LOSS_FRACTION
    else:
        raw = GLP1_STEP_WEIGHT_LOSS_FRACTION * 1.10
    if profile.has_diabetes:
        raw *= GLP1_DIABETES_WEIGHT_LOSS_MULTIPLIER
    return raw * GLP1_DURABLE_EFFECT_FRACTION


def build_glp1_phenotype_model(
    baseline: dict[str, Any],
    profile: Profile,
) -> dict[str, Any]:
    """Phenotype-conditioned GLP-1 model for chronic semaglutide therapy."""
    bmi = profile.bmi_midpoint
    a1c = latest_lab_value(baseline, "HbA1c", 5.4)
    glucose = latest_lab_value(baseline, "Glucose", 90.0)
    cardio_need = float(baseline.get("derived", {}).get("cardio_need", 0.0))
    sleep_breathing_burden = float(
        baseline.get("derived", {})
        .get("sleep_component_burdens", {})
        .get("breathing", 0.0)
    )
    diabetes_signal = 1.0 if profile.has_diabetes or (a1c or 0) >= 6.5 else 0.0
    prediabetes_signal = max(
        clamp(((a1c or 0.0) - 5.6) / 0.8, 0.0, 1.0),
        clamp(((glucose or 0.0) - 100.0) / 25.0, 0.0, 1.0),
    )
    cardiometabolic_signal = clamp(
        0.45 * cardio_need
        + 0.25 * prediabetes_signal
        + 0.20 * float(profile.has_hypertension)
        + 0.20 * diabetes_signal
        + 0.10 * float(profile.smoking_status == "current")
        + 0.10 * clamp((profile.age - 45) / 20.0, 0.0, 1.0),
        0.0,
        1.0,
    )
    durable_weight_loss_fraction = glp1_weight_loss_fraction(
        profile,
        cardiometabolic_signal=cardiometabolic_signal,
    )
    excess_bmi_fraction = max(0.0, (bmi - 25.0) / bmi)
    excess_bmi_reversal_fraction = (
        0.0
        if excess_bmi_fraction == 0.0
        else clamp(durable_weight_loss_fraction / excess_bmi_fraction, 0.0, 1.0)
    )
    obesity_qol_disutility = glp1_obesity_qol_disutility(profile.bmi_category)
    annual_weight_qol_gain = obesity_qol_disutility * excess_bmi_reversal_fraction
    annual_glycemic_qol_gain = 0.0015 * diabetes_signal + 0.0007 * prediabetes_signal
    lean_mass_penalty_rate = 0.006 if profile.activity_level in {"active", "moderate"} else 0.010
    annual_lean_mass_penalty = durable_weight_loss_fraction * lean_mass_penalty_rate
    annual_off_label_penalty = 0.001 if profile.bmi_category == "normal" else 0.0
    net_qol_annual = (
        annual_weight_qol_gain
        + annual_glycemic_qol_gain
        - annual_lean_mass_penalty
        - annual_off_label_penalty
    )

    if profile.bmi_category == "normal":
        cv_transport = 0.0
    else:
        cv_transport = clamp(
            0.12
            + 0.35 * cardiometabolic_signal
            + 0.15 * diabetes_signal
            + 0.10 * float(profile.bmi_category in {"obese", "severely_obese"})
            + 0.08 * float(profile.age >= 50),
            0.0,
            0.85,
        )
        if profile.age < 45 and diabetes_signal == 0.0:
            cv_transport *= 0.55
    observed_hr = profile_adjusted_observed_hr(GLP1_ALL_CAUSE_PROXY_HR, cv_transport)

    adiposity_signal = clamp((bmi - 25.0) / 10.0, 0.0, 1.0)
    weight_loss_signal = clamp(durable_weight_loss_fraction / 0.10, 0.0, 1.0)
    sleep_relief_signal = adiposity_signal * weight_loss_signal
    sleep_component_relief = {
        "breathing": round(0.18 * sleep_relief_signal, 4),
        "daytime": round(0.06 * sleep_relief_signal, 4),
        "quality": round(0.04 * sleep_relief_signal, 4),
    }
    if sleep_breathing_burden <= 0:
        sleep_component_relief = {key: 0.0 for key in sleep_component_relief}

    return {
        "bmi_category": profile.bmi_category,
        "bmi_midpoint": bmi,
        "a1c": a1c,
        "glucose": glucose,
        "cardio_need": round(cardio_need, 4),
        "diabetes_signal": round(diabetes_signal, 4),
        "prediabetes_signal": round(prediabetes_signal, 4),
        "cardiometabolic_signal": round(cardiometabolic_signal, 4),
        "durable_weight_loss_fraction": round(durable_weight_loss_fraction, 4),
        "excess_bmi_reversal_fraction": round(excess_bmi_reversal_fraction, 4),
        "annual_weight_qol_gain": round(annual_weight_qol_gain, 6),
        "annual_glycemic_qol_gain": round(annual_glycemic_qol_gain, 6),
        "annual_lean_mass_penalty": round(annual_lean_mass_penalty, 6),
        "annual_off_label_penalty": round(annual_off_label_penalty, 6),
        "net_qol_annual": round(net_qol_annual, 6),
        "cv_transport": round(cv_transport, 4),
        "observed_hr": round(observed_hr, 6),
        "all_cause_proxy_hr_source": GLP1_ALL_CAUSE_PROXY_HR,
        "sleep_component_relief": sleep_component_relief,
    }


def build_semaglutide_spec(
    baseline: dict[str, Any],
    profile: Profile,
) -> StackSpec:
    model = build_glp1_phenotype_model(baseline, profile)
    is_weight_indicated = profile.bmi_category != "normal"
    phenotype_note = (
        "No obesity, diabetes, hypertension, or strong cardiometabolic signal is present, "
        "so benefits are zeroed except for a small off-label lean-mass/appetite downside."
        if not is_weight_indicated
        else (
            f"Modeled durable weight loss of "
            f"{model['durable_weight_loss_fraction']:.1%}, recovering "
            f"{model['excess_bmi_reversal_fraction']:.0%} of excess-BMI function burden."
        )
    )
    return make_spec(
        "semaglutide",
        observed_hr=float(model["observed_hr"]),
        log_sd=0.10,
        conf_alpha=2.2 if is_weight_indicated else 1.3,
        conf_beta=4.8 if is_weight_indicated else 7.0,
        qol_annual=float(model["net_qol_annual"]),
        qol_years=10,
        low_qaly=-0.12,
        high_qaly=0.16 if is_weight_indicated else 0.01,
        personalization=(
            "GLP-1 model now keys off BMI category, glycemia, hypertension, age, "
            f"and lipid/metabolic signal. {phenotype_note}"
        ),
        rationale=(
            "Semaglutide is modeled as chronic obesity/metabolic therapy, not a generic "
            "longevity peptide: STEP weight loss and HRQoL effects feed a function/QOL "
            "overlay, SELECT informs only a transported hard-outcome proxy, and GI plus "
            "biliary/pancreatic harms still apply."
        ),
        sources=GLP1_SOURCES,
        general_qol_utility_weight_ids=WEIGHT_RELATED_FUNCTION_QOL,
        general_qol_lineage_note=(
            "Weight-loss utility is mapped to function and sleep-residual fallback weights; "
            "the model stores explicit phenotype components in assumptions.model_details."
        ),
        sleep_component_relief={
            key: float(value)
            for key, value in model["sleep_component_relief"].items()
            if float(value) > 0.0
        },
        apply_profile_effect_rules=False,
        model_details=model,
    )


def apply_joint_fall_pathway(
    spec: StackSpec,
    *,
    age: int,
    activity_level: str,
    joint_multiplier: float,
) -> StackSpec:
    """Add a small age-gated fall/fracture pathway on top of joint-symptom relief.

    The direct evidence for most joint-support supplements is symptom/QOL-oriented.
    This helper adds a much smaller downstream fall/fracture pathway that grows with
    age and lower mobility reserve rather than pretending joint items directly move
    hard outcomes at all ages.
    """
    resolved = resolve_stack_spec(spec)
    base_qol_annual = max(resolved.qol_annual, 0.0)
    if base_qol_annual <= 0:
        return spec

    # Mobility/fall-related quality spillovers can start to matter modestly from
    # midlife onward, but fracture-mediated mortality should turn on later.
    qol_age_gate = clamp((age - 35.0) / 30.0, 0.0, 1.0)
    mortality_age_gate = clamp((age - 55.0) / 20.0, 0.0, 1.0)
    if qol_age_gate <= 0 and mortality_age_gate <= 0:
        return spec

    activity_modifier = {
        "sedentary": 1.05,
        "light": 1.0,
        "active": 0.85,
    }.get(activity_level, 1.0)
    fall_susceptibility = clamp((0.20 + 0.80 * joint_multiplier) * activity_modifier, 0.0, 1.0)
    qol_fall_pathway = qol_age_gate * fall_susceptibility
    mortality_fall_pathway = mortality_age_gate * fall_susceptibility

    # Small indirect QoL effect via mobility confidence / fewer minor falls.
    indirect_qol_annual = base_qol_annual * 0.25 * qol_fall_pathway

    # Tiny mortality signal via fracture prevention; this should stay much smaller
    # than the direct symptom/QOL channel, especially in younger adults.
    mortality_scale = min(base_qol_annual / 0.0008, 2.0)
    fall_mortality_log_reduction = 0.01 * mortality_fall_pathway * mortality_scale
    adjusted_hr = math.exp(math.log(resolved.observed_hr) - fall_mortality_log_reduction)

    return replace(
        spec,
        observed_hr=adjusted_hr,
        qol_annual=base_qol_annual + indirect_qol_annual,
        rationale=(
            resolved.rationale
            + " A much smaller downstream fall/fracture pathway is included with age gating."
        ),
        personalization=(
            resolved.personalization
            + " Any fall/fracture benefit is modeled as much smaller and grows mainly with age."
        ),
    )


def discount_factor(years: float, rate: float = QALY_DISCOUNT_RATE) -> float:
    """Present-value multiplier for an annual QOL stream.

    ``qol_years`` enters through ``StackSpec`` resolution as a float, even when
    the author wrote integer literals. Handle fractional durations by adding
    the pro-rated final year at the next discount period.
    """
    if years <= 0:
        return 0.0
    full_years = int(math.floor(years))
    remainder = years - full_years
    total = sum((1.0 / ((1.0 + rate) ** t)) for t in range(full_years))
    if remainder:
        total += remainder / ((1.0 + rate) ** full_years)
    return total


def modeled_total_cost(
    annual_cost: float | None,
    years: float,
    rate: float = COST_DISCOUNT_RATE,
) -> float:
    """Discounted cost over the same modeled duration as QOL effects."""
    if annual_cost is None:
        return 0.0
    return float(annual_cost) * discount_factor(years, rate)


def cost_per_qaly(total_cost: float, total_qaly: float) -> float | None:
    if total_cost <= 0 or total_qaly <= 0:
        return None
    return total_cost / total_qaly


def reference_case_payload() -> dict[str, Any]:
    """Reference-case assumptions and current-protocol compliance metadata."""
    discounting_matches_reference_case = (
        abs(QALY_DISCOUNT_RATE - DEFAULT_REFERENCE_CASE.health_discount_rate) < 1e-12
        and abs(COST_DISCOUNT_RATE - DEFAULT_REFERENCE_CASE.cost_discount_rate) < 1e-12
    )
    return {
        "base": DEFAULT_REFERENCE_CASE.to_dict(),
        "discount_sensitivity_rates": list(REFERENCE_CASE_SENSITIVITY_RATES),
        "utility_source_priority": [
            {
                "instrument": instrument,
                "status": utility_reference_case_status(instrument),
            }
            for instrument in DEFAULT_REFERENCE_CASE.utility_preference_order
        ],
        "current_protocol_model": {
            "health_discount_rate": QALY_DISCOUNT_RATE,
            "cost_discount_rate": COST_DISCOUNT_RATE,
            "discounting_matches_reference_case": discounting_matches_reference_case,
            "is_formal_reference_case": False,
            "reference_case_alignment": (
                "reference_case_discounting_with_fallback_utility_lineage"
                if discounting_matches_reference_case
                else "fallback_utility_lineage_only"
            ),
            "gap": (
                "The current personal protocol model now uses reference-case discounting. Sleep, "
                "sexual-function, hair, GI, musculoskeletal, vision, stress, and functional QOL "
                "overlays carry explicit utility lineage; rows without a defensible mapped utility "
                "source get no generic QOL overlay. Some symptom overlays and direct harms still "
                "use disability-weight fallback lineage rather than preferred EQ-5D/SF-6D/HUI "
                "sources, so the output is reference-case aligned, not a formal reference-case "
                "cost-utility analysis."
            ),
        },
    }


def profile_adjusted_observed_hr(observed_hr: float, multiplier: float) -> float:
    """Apply catalog profile/genetic transport rules to a resolved HR."""
    if observed_hr <= 0:
        raise ValueError(f"Observed HR must be positive, got {observed_hr}")
    if math.isclose(multiplier, 1.0, rel_tol=0.0, abs_tol=1e-12):
        return observed_hr
    return float(math.exp(math.log(observed_hr) * multiplier))


def profile_payload(profile: Profile) -> dict[str, Any]:
    """Serialize profile fields without leaking derived genetic details."""
    payload = asdict(replace(profile, genetic_profile=None))
    genetic_profile = getattr(profile, "genetic_profile", None)
    if genetic_profile is None:
        payload["genetic_profile"] = None
    else:
        payload["genetic_profile"] = {
            "available": True,
            "phenotype_count": len(getattr(genetic_profile, "phenotypes", {})),
            "actionable_finding_count": len(
                getattr(genetic_profile, "actionable_findings", []),
            ),
            "chip_version": getattr(genetic_profile, "chip_version", None),
        }
    return payload


def matching_genetic_rule_rationales(
    entry: CatalogEntry,
    profile: Profile,
) -> list[str]:
    genetic_profile = getattr(profile, "genetic_profile", None)
    if genetic_profile is None:
        return []
    rationales = []
    for rule in entry.genetic_effect_rules:
        if rule.matches(genetic_profile):
            rationales.append(rule.rationale)
    return rationales


REFERENCE_CASE_READY_UTILITY_STATUSES = {"reference_case", "acceptable_mapped"}
UTILITY_LINEAGE_STATUSES = REFERENCE_CASE_READY_UTILITY_STATUSES | {
    "fallback",
    "non_reference_case",
}


def utility_weight_lineage_payload(
    weight_ids: tuple[str, ...],
    *,
    note: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Serialize named utility weights with reference-case status attached."""
    lineage: dict[str, dict[str, Any]] = {}
    for weight_id in weight_ids:
        weight = get_public_health_utility_weight(weight_id)
        payload = weight.to_dict()
        if note:
            payload["lineage_note"] = note
        lineage[weight_id] = payload
    return lineage


def general_qol_utility_lineage(
    resolved: ResolvedStackSpec,
) -> dict[str, dict[str, Any]]:
    """Return public-health utility lineage for a hand-estimated general-QOL overlay."""
    lineage = utility_weight_lineage_payload(
        resolved.general_qol_utility_weight_ids,
        note=resolved.general_qol_lineage_note,
    )
    for payload in lineage.values():
        utility_decrement = float(payload["utility_decrement"])
        payload["annual_utility_overlay"] = round(resolved.qol_annual, 6)
        payload["overlay_fraction_of_utility_decrement"] = (
            None
            if utility_decrement <= 0
            else round(abs(resolved.qol_annual) / utility_decrement, 6)
        )
    return lineage


def distribution_payload(distribution: Distribution | None) -> dict[str, Any] | None:
    """Serialize an Optiqal distribution without relying on a dataclass round-trip."""
    if distribution is None:
        return None
    return {
        "type": distribution.type,
        "params": dict(distribution.params),
    }


def direct_harm_utility_lineage(item_id: str) -> dict[str, dict[str, Any]]:
    """Return explicit utility lineage for catalog direct-harm QALY penalties."""
    catalog_entry = CATALOG[item_id]
    return harm_utility_lineage_payload(catalog_entry.harm_effects)


def triggered_interaction_rules(
    item_id: str,
    active_interaction_tags: tuple[str, ...] = (),
) -> list[Any]:
    """Return stack-aware interaction rules activated for an item."""
    catalog_entry = CATALOG[item_id]
    tag_counts = Counter(active_interaction_tags)
    for tag in catalog_entry.interaction_tags:
        tag_counts[tag] += 1

    triggered = []
    for rule in catalog_entry.interaction_rules:
        threshold = rule.minimum_matches or len(rule.requires_tags)
        matches = sum(tag_counts[tag] for tag in rule.requires_tags)
        if matches >= threshold and all(tag_counts[tag] > 0 for tag in rule.requires_tags):
            triggered.append(allocate_interaction_rule(rule, matches))
    return triggered


def harm_utility_lineage_payload(
    harm_sources: list[Any],
) -> dict[str, dict[str, Any]]:
    """Return explicit utility lineage for direct harms or interaction rules."""
    lineage: dict[str, dict[str, Any]] = {}
    for harm in harm_sources:
        weight_ids = HARM_UTILITY_WEIGHT_IDS.get(harm.id, ())
        note = (
            "Direct-harm QALY penalty is anchored to this fallback health-state utility; "
            "the catalog still owns the event probability or annual loss magnitude."
        )
        lineage[harm.id] = {
            "id": harm.id,
            "description": harm.description,
            "source": harm.source,
            "annual_qaly_loss": distribution_payload(harm.annual_qaly_loss),
            "event_probability": distribution_payload(harm.event_probability),
            "event_qaly_loss": distribution_payload(harm.event_qaly_loss),
            "max_events": harm.max_events,
            "utility_lineage": utility_weight_lineage_payload(weight_ids, note=note),
        }
    return lineage


def item_harm_utility_lineage(
    item_id: str,
    active_interaction_tags: tuple[str, ...] = (),
) -> dict[str, dict[str, Any]]:
    """Return direct plus triggered interaction harm lineage for an item."""
    catalog_entry = CATALOG[item_id]
    harms = list(catalog_entry.harm_effects)
    harms.extend(triggered_interaction_rules(item_id, active_interaction_tags))
    return harm_utility_lineage_payload(harms)


def flatten_direct_harm_utility_lineage(
    direct_harm_lineage: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Flatten nested harm utility sources for component-status summarization."""
    flattened: dict[str, dict[str, Any]] = {}
    for harm_id, harm_payload in direct_harm_lineage.items():
        for weight_id, source in harm_payload.get("utility_lineage", {}).items():
            flattened[f"{harm_id}:{weight_id}"] = source
    return flattened


def utility_lineage_component_status(
    lineage: dict[str, dict[str, Any]],
    *,
    empty_status: str,
) -> str:
    """Summarize reference-case status across one component's utility sources."""
    statuses = {str(source.get("reference_case_status")) for source in lineage.values()}
    if not statuses:
        return empty_status
    if not statuses <= UTILITY_LINEAGE_STATUSES:
        return "needs_preference_based_utility_validation"
    if "non_reference_case" in statuses:
        return "non_reference_case"
    if "fallback" in statuses:
        return "fallback"
    if "acceptable_mapped" in statuses:
        return "acceptable_mapped"
    return "reference_case"


def qaly_lineage_payload(
    *,
    resolved: ResolvedStackSpec,
    mortality_qaly: float,
    direct_harm_qaly: float,
    general_qol_qaly: float,
    sleep_qol_qaly: float,
    direct_harm_lineage: dict[str, dict[str, Any]] | None = None,
    sleep_lineage: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Describe whether each QALY component is reference-case ready."""
    issues: list[str] = []
    general_lineage = general_qol_utility_lineage(resolved)
    general_status = utility_lineage_component_status(
        general_lineage,
        empty_status="needs_preference_based_utility_source",
    )
    direct_lineage = direct_harm_lineage or {}
    direct_weight_lineage = flatten_direct_harm_utility_lineage(direct_lineage)
    direct_status = utility_lineage_component_status(
        direct_weight_lineage,
        empty_status="needs_utility_lineage",
    )
    if abs(general_qol_qaly) > 1e-12:
        if not general_lineage:
            issues.append("general_qol_needs_preference_based_utility_source")
        elif general_status == "needs_preference_based_utility_validation":
            issues.append("general_qol_needs_preference_based_utility_validation")
        elif general_status == "fallback":
            issues.append("general_qol_uses_fallback_disability_weights")
        elif general_status == "non_reference_case":
            issues.append("general_qol_uses_non_reference_case_utility")
    if abs(sleep_qol_qaly) > 1e-12:
        sleep_status = utility_lineage_component_status(
            sleep_lineage or {},
            empty_status="needs_preference_based_utility_validation",
        )
        if sleep_status == "needs_preference_based_utility_validation":
            issues.append("sleep_qol_needs_mapped_preference_based_utility_validation")
        elif sleep_status == "fallback":
            issues.append("sleep_qol_uses_fallback_disability_weights")
        elif sleep_status == "non_reference_case":
            issues.append("sleep_qol_uses_non_reference_case_utility")
    if abs(direct_harm_qaly) > 1e-12:
        if not direct_lineage or not direct_weight_lineage:
            issues.append("direct_harm_needs_event_probability_and_utility_lineage")
        elif direct_status in {
            "needs_utility_lineage",
            "needs_preference_based_utility_validation",
        }:
            issues.append("direct_harm_needs_event_probability_and_utility_validation")
        elif direct_status == "fallback":
            issues.append("direct_harm_uses_fallback_disability_weights")
        elif direct_status == "non_reference_case":
            issues.append("direct_harm_uses_non_reference_case_utility")

    needs_lineage = any("needs_" in issue for issue in issues)
    uses_fallback = any("uses_fallback" in issue for issue in issues)
    uses_non_reference = any("uses_non_reference" in issue for issue in issues)

    return {
        "overall_reference_case_status": (
            "needs_utility_lineage"
            if needs_lineage
            else "non_reference_case_utility_lineage"
            if uses_non_reference
            else "fallback_utility_lineage"
            if uses_fallback
            else "reference_case_ready"
        ),
        "issues": issues,
        "components": {
            "mortality": {
                "qaly": round(mortality_qaly, 6),
                "method": "life_table_simulation",
                "reference_case_status": "reference_case_ready",
            },
            "direct_harm": {
                "qaly": round(direct_harm_qaly, 6),
                "method": "harm_model_annual_or_event_loss",
                "reference_case_status": (
                    "not_applicable"
                    if abs(direct_harm_qaly) <= 1e-12
                    else direct_status
                ),
                "utility_lineage": direct_lineage,
            },
            "general_qol": {
                "qaly": round(general_qol_qaly, 6),
                "annual_utility": round(resolved.qol_annual, 6),
                "method": "annual_utility_overlay",
                "reference_case_status": (
                    "not_applicable"
                    if abs(general_qol_qaly) <= 1e-12
                    else general_status
                ),
                "utility_lineage": general_lineage,
            },
            "sleep_qol": {
                "qaly": round(sleep_qol_qaly, 6),
                "method": "sleep_burden_component_mapping",
                "reference_case_status": (
                    "not_applicable"
                    if abs(sleep_qol_qaly) <= 1e-12
                    else utility_lineage_component_status(
                        sleep_lineage or {},
                        empty_status="needs_preference_based_utility_validation",
                    )
                ),
                "utility_lineage": sleep_lineage or {},
            },
        },
    }


def status_for_category(category: str) -> str:
    return {
        "rx_current": "taking",
        "rx_candidate": "considering",
        "supplement_current": "taking",
        "supplement_bought": "testing",
        "supplement_candidate": "watching",
        "sleep_current": "taking",
        "sleep_candidate": "watching",
    }.get(category, "watching")


def is_actionable_item(item: dict[str, Any]) -> bool:
    return str(item.get("status", "")) in ACTIONABLE_STATUSES


def current_stack_interaction_tags(
    protocol_items: list[dict[str, Any]],
    *,
    exclude_item_id: str | None = None,
) -> tuple[str, ...]:
    """Return active interaction tags from the current stack, optionally excluding one item."""
    tags: list[str] = []
    for item in protocol_items:
        item_id = str(item.get("id", ""))
        if item_id == exclude_item_id:
            continue
        if str(item.get("status", "")) not in CURRENT_STACK_STATUSES:
            continue
        catalog_entry = CATALOG.get(item_id)
        if catalog_entry is None:
            continue
        tags.extend(catalog_entry.interaction_tags)
    return tuple(tags)


def stable_random_seed(*parts: str) -> int:
    """Return a deterministic seed for item/component-level Monte Carlo draws."""
    digest = hashlib.blake2b("|".join(parts).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % (2**32)


def qol_uncertainty_relative_sd(evidence_quality: str | None) -> float:
    return QOL_UNCERTAINTY_RELATIVE_SD_BY_EVIDENCE.get(
        str(evidence_quality or "").lower(),
        DEFAULT_QOL_UNCERTAINTY_RELATIVE_SD,
    )


def sample_qol_component_draws(
    mean_qaly: float,
    *,
    item_id: str,
    component: str,
    evidence_quality: str | None,
    n_simulations: int = N_SIMULATIONS,
) -> np.ndarray:
    """Sample QOL overlay uncertainty while preserving the authored mean."""
    if abs(mean_qaly) <= 1e-12:
        return np.zeros(n_simulations)
    relative_sd = qol_uncertainty_relative_sd(evidence_quality)
    rng = np.random.default_rng(stable_random_seed(item_id, component, "qol"))
    draws = rng.normal(
        loc=mean_qaly,
        scale=abs(mean_qaly) * relative_sd,
        size=n_simulations,
    )
    return draws + (mean_qaly - float(np.mean(draws)))


def _standardize_draws(draws: np.ndarray) -> np.ndarray:
    """Return zero-mean, unit-SD draws when possible."""
    standardized = np.asarray(draws, dtype=float)
    sd = float(np.std(standardized))
    if sd <= 1e-12:
        return np.zeros_like(standardized)
    return (standardized - float(np.mean(standardized))) / sd


def latent_protocol_factor(name: str, n_simulations: int = N_SIMULATIONS) -> np.ndarray:
    """Stable latent-world factor used to pair protocol-state counterfactuals."""
    rng = np.random.default_rng(stable_random_seed("protocol_latent", name))
    return _standardize_draws(rng.normal(size=n_simulations))


def _combined_latent_mechanism_factor(
    item_id: str,
    entry: CatalogEntry,
    n_simulations: int = N_SIMULATIONS,
) -> np.ndarray | None:
    tags = [
        f"benefit:{tag}"
        for tag in sorted(set(entry.benefit_tags))
    ]
    tags.extend(
        f"interaction:{tag}"
        for tag in sorted(set(entry.interaction_tags))
    )
    if not tags:
        return None
    factors = [
        latent_protocol_factor(tag, n_simulations)
        for tag in tags
    ]
    return _standardize_draws(np.sum(factors, axis=0) / math.sqrt(len(factors)))


def latent_protocol_item_score(
    item_id: str,
    entry: CatalogEntry | None = None,
    n_simulations: int = N_SIMULATIONS,
) -> np.ndarray:
    """Return the latent-world ordering score for one protocol item.

    Higher scores represent worlds where this item is a better personal fit.
    The score is intentionally shared across related items through global,
    mechanism, and category factors, with item-specific residual variation.
    """
    entry = entry or CATALOG[item_id]
    weighted_components: list[tuple[float, np.ndarray]] = [
        (LATENT_GLOBAL_SCORE_WEIGHT, latent_protocol_factor("global_fit", n_simulations)),
        (
            LATENT_CATEGORY_SCORE_WEIGHT,
            latent_protocol_factor(
                f"category:{public_display_category(entry)}",
                n_simulations,
            ),
        ),
    ]
    mechanism_factor = _combined_latent_mechanism_factor(item_id, entry, n_simulations)
    if mechanism_factor is not None:
        weighted_components.append((LATENT_MECHANISM_SCORE_WEIGHT, mechanism_factor))

    shared_weight_sq = sum(weight * weight for weight, _ in weighted_components)
    max_weight_sq = LATENT_MAX_SHARED_SCORE_WEIGHT ** 2
    if shared_weight_sq > max_weight_sq:
        scale = math.sqrt(max_weight_sq / shared_weight_sq)
        weighted_components = [
            (weight * scale, component)
            for weight, component in weighted_components
        ]
        shared_weight_sq = max_weight_sq

    residual_weight = math.sqrt(max(0.0, 1.0 - shared_weight_sq))
    residual = latent_protocol_factor(f"item:{item_id}:residual", n_simulations)
    score = residual_weight * residual
    for weight, component in weighted_components:
        score += weight * component
    return _standardize_draws(score)


def rank_preserving_latent_draws(
    draws: np.ndarray,
    score: np.ndarray,
) -> np.ndarray:
    """Reorder item draws by latent-world score without changing the marginal."""
    draws = np.asarray(draws, dtype=float)
    if draws.size != score.size:
        raise ValueError(
            f"draw/score size mismatch: {draws.size} draws vs {score.size} scores",
        )
    if draws.size == 0 or float(np.std(draws)) <= 1e-12:
        return draws.copy()
    order = np.argsort(score, kind="mergesort")
    sorted_draws = np.sort(draws)
    reordered = np.empty_like(draws)
    reordered[order] = sorted_draws
    return reordered


def latent_protocol_item_draws(
    item_id: str,
    estimate: dict[str, Any],
) -> np.ndarray:
    """Return item draws paired to shared latent protocol worlds."""
    cached = estimate.get("_latent_total_draws")
    if cached is not None:
        return cached
    score = latent_protocol_item_score(item_id)
    draws = rank_preserving_latent_draws(estimate["_total_draws"], score)
    estimate["_latent_total_draws"] = draws
    return draws


def load_protocol_items(context: ProtocolContext | None = None) -> list[dict[str, Any]]:
    context = resolve_protocol_context(context)
    existing = {}
    if context.protocol_json.exists():
        data = json.loads(context.protocol_json.read_text())
        existing = {item["id"]: item for item in data.get("supplements", [])}

    items = []
    for entry in CATALOG.values():
        prior = existing.get(entry.id, {})
        items.append({
            "id": entry.id,
            "name": entry.name,
            "status": prior.get("status", status_for_category(entry.category)),
            "category": entry.category,
            "display_category": public_display_category(entry),
            "annual_cost": entry.annual_cost,
            "dose_notes": prior.get("dose_notes"),
            "time_of_day": prior.get("time_of_day"),
        })
    return items


def cost_effectiveness_sort_key(item: dict[str, Any]) -> tuple[float, float]:
    """Sort positive-QALY items by practical cost effectiveness.

    Free beneficial behavior changes are treated as dominant and sorted ahead
    of paid items; paid items sort by modeled dollars per QALY.
    """
    if item["total_qaly"] <= 0:
        return (math.inf, math.inf)
    if item["modeled_total_cost"] <= 0:
        return (-1.0, -item["total_qaly"])
    cost_per = item["cost_per_qaly"]
    if cost_per is None:
        return (math.inf, math.inf)
    return (float(cost_per), -item["total_qaly"])


def ranking_projection(item: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "name",
        "status",
        "category",
        "display_category",
        "annual_cost",
        "modeled_total_cost",
        "cost_per_qaly",
        "total_qaly",
        "days",
        "p_benefit",
        "p_harm",
    )
    return {field: item.get(field) for field in fields}


def build_decision_rankings(estimates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    actionable = [item for item in estimates if is_actionable_item(item)]
    positive_actionable = [item for item in actionable if item["total_qaly"] > 0]
    paid_positive_actionable = [
        item for item in positive_actionable if item["modeled_total_cost"] > 0
    ]
    supplement_candidates = [
        item for item in positive_actionable if item["display_category"] == "supplement"
    ]
    free_positive_actionable = [
        item for item in positive_actionable if item["modeled_total_cost"] <= 0
    ]
    negative_actionable = [item for item in actionable if item["total_qaly"] < 0]

    return {
        "actionable_by_total_qaly": [
            ranking_projection(item)
            for item in sorted(
                positive_actionable,
                key=lambda item: item["total_qaly"],
                reverse=True,
            )[:15]
        ],
        "actionable_by_cost_per_qaly": [
            ranking_projection(item)
            for item in sorted(paid_positive_actionable, key=cost_effectiveness_sort_key)[:15]
        ],
        "supplement_candidates_by_cost_per_qaly": [
            ranking_projection(item)
            for item in sorted(supplement_candidates, key=cost_effectiveness_sort_key)[:15]
        ],
        "free_positive_actions": [
            ranking_projection(item)
            for item in sorted(
                free_positive_actionable,
                key=lambda item: item["total_qaly"],
                reverse=True,
            )[:10]
        ],
        "negative_actionable": [
            ranking_projection(item)
            for item in sorted(negative_actionable, key=lambda item: item["total_qaly"])[:15]
        ],
    }


def query_one(conn: sqlite3.Connection, sql: str) -> sqlite3.Row:
    row = conn.execute(sql).fetchone()
    if row is None:
        raise RuntimeError(f"Query returned no rows: {sql}")
    return row


def load_baseline(context: ProtocolContext | None = None) -> dict[str, Any]:
    context = resolve_protocol_context(context)
    conn = sqlite3.connect(context.health_db)
    conn.row_factory = sqlite3.Row

    sleep_90 = query_one(
        conn,
        """
        WITH recent AS (
          SELECT * FROM sleep_nights WHERE date >= date('now', '-90 day')
        )
        SELECT
          COUNT(*) AS nights,
          AVG(whoop_sleep_hours) AS whoop_sleep_h,
          AVG(whoop_sleep_perf) AS whoop_sleep_perf,
          AVG(whoop_recovery) AS whoop_recovery,
          AVG(whoop_spo2) AS whoop_spo2,
          AVG(eight_score) AS eight_score,
          AVG(eight_quality_score) AS eight_quality,
          AVG(eight_routine_score) AS eight_routine,
          AVG(eight_sleep_min) / 60.0 AS eight_sleep_h,
          AVG(eight_waso_min) AS eight_waso
          ,
          AVG(eight_latency_min) AS eight_latency,
          AVG(eight_breathing_score) AS eight_breathing,
          AVG(eight_social_jetlag_min) AS eight_social_jetlag,
          AVG(eight_snore_pct) AS eight_snore_pct,
          AVG(eight_sleep_debt_min) AS eight_sleep_debt
        FROM recent
        """,
    )
    sleep_30 = query_one(
        conn,
        """
        WITH recent AS (
          SELECT * FROM sleep_nights WHERE date >= date('now', '-30 day')
        )
        SELECT
          COUNT(*) AS nights,
          AVG(whoop_sleep_hours) AS whoop_sleep_h,
          AVG(whoop_sleep_perf) AS whoop_sleep_perf,
          AVG(whoop_recovery) AS whoop_recovery,
          AVG(whoop_spo2) AS whoop_spo2,
          AVG(eight_score) AS eight_score,
          AVG(eight_quality_score) AS eight_quality,
          AVG(eight_routine_score) AS eight_routine,
          AVG(eight_sleep_min) / 60.0 AS eight_sleep_h,
          AVG(eight_waso_min) AS eight_waso
          ,
          AVG(eight_latency_min) AS eight_latency,
          AVG(eight_breathing_score) AS eight_breathing,
          AVG(eight_social_jetlag_min) AS eight_social_jetlag,
          AVG(eight_snore_pct) AS eight_snore_pct,
          AVG(eight_sleep_debt_min) AS eight_sleep_debt
        FROM recent
        """,
    )
    sleep_pre = query_one(
        conn,
        """
        WITH recent AS (
          SELECT * FROM sleep_nights
          WHERE date >= date('now', '-15 day') AND date < date('now', '-7 day')
        )
        SELECT
          COUNT(*) AS nights,
          AVG(whoop_recovery) AS whoop_recovery,
          AVG(whoop_spo2) AS whoop_spo2,
          AVG(eight_quality_score) AS eight_quality,
          AVG(eight_waso_min) AS eight_waso,
          AVG(eight_latency_min) AS eight_latency,
          AVG(eight_breathing_score) AS eight_breathing,
          AVG(eight_snore_pct) AS eight_snore_pct
        FROM recent
        """,
    )
    sleep_post = query_one(
        conn,
        """
        WITH recent AS (
          SELECT * FROM sleep_nights
          WHERE date >= date('now', '-7 day')
        )
        SELECT
          COUNT(*) AS nights,
          AVG(whoop_recovery) AS whoop_recovery,
          AVG(whoop_spo2) AS whoop_spo2,
          AVG(eight_quality_score) AS eight_quality,
          AVG(eight_waso_min) AS eight_waso,
          AVG(eight_latency_min) AS eight_latency,
          AVG(eight_breathing_score) AS eight_breathing,
          AVG(eight_snore_pct) AS eight_snore_pct
        FROM recent
        """,
    )
    training_180 = query_one(
        conn,
        """
        WITH recent AS (
          SELECT * FROM sleep_nights
          WHERE date >= date('now', '-180 day')
            AND whoop_strain IS NOT NULL
        )
        SELECT
          COUNT(*) AS days,
          AVG(whoop_strain) AS avg_strain,
          AVG(whoop_recovery) AS avg_recovery,
          AVG(whoop_hrv) AS avg_hrv,
          AVG(whoop_rhr) AS avg_rhr,
          AVG(whoop_sleep_hours) AS avg_sleep_h,
          AVG(whoop_sleep_perf) AS avg_sleep_perf,
          AVG(CASE WHEN whoop_strain >= 14 THEN 1.0 ELSE 0.0 END) AS high_strain_share,
          AVG(CASE WHEN whoop_strain >= 16 THEN 1.0 ELSE 0.0 END) AS very_high_strain_share
        FROM recent
        """,
    )
    target_markers = [
        "LDL",
        "HDL",
        "Triglycerides",
        "HbA1c",
        "Glucose",
        "Vitamin D",
        "TSH",
        "eGFR",
        "Creatinine",
    ]
    labs = {}
    for marker in target_markers:
        row = conn.execute(
            """
            SELECT value
            FROM bloodwork
            WHERE marker = ?
            ORDER BY date DESC
            LIMIT 1
            """,
            (marker,),
        ).fetchone()
        labs[marker] = row["value"] if row else None
    latest_lab_date = query_one(
        conn,
        "SELECT MAX(date) AS latest_lab_date FROM bloodwork",
    )["latest_lab_date"]
    latest_body_comp = conn.execute(
        """
        SELECT date, weight_kg, body_fat_pct, muscle_mass_kg, source
        FROM body_comp
        ORDER BY date DESC
        LIMIT 1
        """
    ).fetchone()
    body_comp_180 = query_one(
        conn,
        """
        WITH recent AS (
          SELECT * FROM body_comp
          WHERE date >= date('now', '-180 day')
        )
        SELECT
          COUNT(*) AS days,
          AVG(weight_kg) AS avg_weight_kg,
          AVG(body_fat_pct) AS avg_body_fat_pct,
          AVG(muscle_mass_kg) AS avg_muscle_mass_kg
        FROM recent
        """,
    )
    conn.close()

    combined_sleep = (
        float(sleep_90["whoop_sleep_h"] or 0.0) + float(sleep_90["eight_sleep_h"] or 0.0)
    ) / 2.0
    airway_response_signal = estimate_airway_response_signal(
        SleepMetrics(
            recovery_score=float(sleep_pre["whoop_recovery"] or 0.0),
            sleep_quality_score=float(sleep_pre["eight_quality"] or 0.0),
            waso_min=float(sleep_pre["eight_waso"] or 0.0),
            latency_min=float(sleep_pre["eight_latency"] or 0.0),
            breathing_score=float(sleep_pre["eight_breathing"] or 0.0),
            spo2=float(sleep_pre["whoop_spo2"] or 0.0),
            snore_pct=float(sleep_pre["eight_snore_pct"] or 0.0),
        ),
        SleepMetrics(
            recovery_score=float(sleep_post["whoop_recovery"] or 0.0),
            sleep_quality_score=float(sleep_post["eight_quality"] or 0.0),
            waso_min=float(sleep_post["eight_waso"] or 0.0),
            latency_min=float(sleep_post["eight_latency"] or 0.0),
            breathing_score=float(sleep_post["eight_breathing"] or 0.0),
            spo2=float(sleep_post["whoop_spo2"] or 0.0),
            snore_pct=float(sleep_post["eight_snore_pct"] or 0.0),
        ),
    )
    wearable_sleep_estimate = estimate_sleep_burden(
        SleepMetrics(
            duration_hours=combined_sleep,
            recovery_score=float(sleep_90["whoop_recovery"] or 0.0),
            sleep_quality_score=float(sleep_90["eight_quality"] or 0.0),
            waso_min=float(sleep_90["eight_waso"] or 0.0),
            routine_score=float(sleep_90["eight_routine"] or 0.0),
            social_jetlag_min=float(sleep_90["eight_social_jetlag"] or 0.0),
            latency_min=float(sleep_90["eight_latency"] or 0.0),
            breathing_score=float(sleep_90["eight_breathing"] or 0.0),
            spo2=float(sleep_90["whoop_spo2"] or 0.0),
            snore_pct=float(sleep_90["eight_snore_pct"] or 0.0),
            sleep_debt_min=float(sleep_90["eight_sleep_debt"] or 0.0),
            airway_response_signal=airway_response_signal,
        )
    )
    sleep_estimate = apply_sleep_study(wearable_sleep_estimate, context.home_sleep_study)
    sleep_need = clamp(
        0.55 * sleep_estimate.component_burdens["duration"]
        + 0.30 * sleep_estimate.component_burdens["daytime"]
        + 0.15 * sleep_estimate.component_burdens["continuity"],
        0.0,
        1.0,
    )
    recovery_gap = sleep_estimate.component_burdens["daytime"]
    sleep_quality_gap = sleep_estimate.component_burdens["quality"]
    waso_gap = sleep_estimate.component_burdens["continuity"]
    sleep_burden_annual_qaly = sleep_estimate.annual_qaly_loss
    cardio_need = clamp(
        0.6 * clamp((float(labs.get("LDL", 64.0)) - 50.0) / 70.0, 0.0, 1.0)
        + 0.4 * clamp((float(labs.get("Triglycerides", 137.0)) - 100.0) / 150.0, 0.0, 1.0),
        0.0,
        1.0,
    )
    high_strain_share = float(training_180["high_strain_share"] or 0.0)
    very_high_strain_share = float(training_180["very_high_strain_share"] or 0.0)
    avg_rhr = float(training_180["avg_rhr"] or 44.0)
    avg_hrv = float(training_180["avg_hrv"] or 110.0)
    structured_intensity_headroom = clamp(
        1.0
        - (
            0.30 * clamp(high_strain_share / 0.35, 0.0, 1.0)
            + 0.70 * clamp(very_high_strain_share / 0.08, 0.0, 1.0)
        ),
        0.2,
        1.0,
    )
    fitness_signal = clamp(
        0.5 * clamp((50.0 - avg_rhr) / 15.0, 0.0, 1.0)
        + 0.5 * clamp((avg_hrv - 80.0) / 60.0, 0.0, 1.0),
        0.0,
        1.0,
    )
    hiit_headroom = clamp(structured_intensity_headroom * (1.0 - 0.35 * fitness_signal), 0.15, 1.0)
    vitamin_d_need = clamp((30.0 - float(labs.get("Vitamin D", 51.5))) / 20.0, 0.0, 1.0)
    kidney_caution = clamp(
        max(
            (80.0 - float(labs.get("eGFR", 76.0))) / 30.0,
            (float(labs.get("Creatinine", 1.24)) - 1.1) / 0.4,
        ),
        0.0,
        1.0,
    )

    return {
        "sleep_90d": {
            "nights": int(sleep_90["nights"]),
            "whoop_sleep_h": round(float(sleep_90["whoop_sleep_h"] or 0.0), 2),
            "whoop_sleep_perf": round(float(sleep_90["whoop_sleep_perf"] or 0.0), 1),
            "whoop_recovery": round(float(sleep_90["whoop_recovery"] or 0.0), 1),
            "whoop_spo2": round(float(sleep_90["whoop_spo2"] or 0.0), 1),
            "eight_score": round(float(sleep_90["eight_score"] or 0.0), 1),
            "eight_quality": round(float(sleep_90["eight_quality"] or 0.0), 1),
            "eight_routine": round(float(sleep_90["eight_routine"] or 0.0), 1),
            "eight_sleep_h": round(float(sleep_90["eight_sleep_h"] or 0.0), 2),
            "eight_waso": round(float(sleep_90["eight_waso"] or 0.0), 1),
            "eight_latency": round(float(sleep_90["eight_latency"] or 0.0), 1),
            "eight_breathing": round(float(sleep_90["eight_breathing"] or 0.0), 3),
            "eight_social_jetlag": round(float(sleep_90["eight_social_jetlag"] or 0.0), 1),
            "eight_snore_pct": round(float(sleep_90["eight_snore_pct"] or 0.0), 1),
            "eight_sleep_debt": round(float(sleep_90["eight_sleep_debt"] or 0.0), 1),
        },
        "sleep_30d": {
            "nights": int(sleep_30["nights"]),
            "whoop_sleep_h": round(float(sleep_30["whoop_sleep_h"] or 0.0), 2),
            "whoop_sleep_perf": round(float(sleep_30["whoop_sleep_perf"] or 0.0), 1),
            "whoop_recovery": round(float(sleep_30["whoop_recovery"] or 0.0), 1),
            "whoop_spo2": round(float(sleep_30["whoop_spo2"] or 0.0), 1),
            "eight_score": round(float(sleep_30["eight_score"] or 0.0), 1),
            "eight_quality": round(float(sleep_30["eight_quality"] or 0.0), 1),
            "eight_routine": round(float(sleep_30["eight_routine"] or 0.0), 1),
            "eight_sleep_h": round(float(sleep_30["eight_sleep_h"] or 0.0), 2),
            "eight_waso": round(float(sleep_30["eight_waso"] or 0.0), 1),
            "eight_latency": round(float(sleep_30["eight_latency"] or 0.0), 1),
            "eight_breathing": round(float(sleep_30["eight_breathing"] or 0.0), 3),
            "eight_social_jetlag": round(float(sleep_30["eight_social_jetlag"] or 0.0), 1),
            "eight_snore_pct": round(float(sleep_30["eight_snore_pct"] or 0.0), 1),
            "eight_sleep_debt": round(float(sleep_30["eight_sleep_debt"] or 0.0), 1),
        },
        "airway_trial_windows": {
            "pre_nights": int(sleep_pre["nights"]),
            "post_nights": int(sleep_post["nights"]),
            "pre_quality": round(float(sleep_pre["eight_quality"] or 0.0), 1),
            "post_quality": round(float(sleep_post["eight_quality"] or 0.0), 1),
            "pre_waso": round(float(sleep_pre["eight_waso"] or 0.0), 1),
            "post_waso": round(float(sleep_post["eight_waso"] or 0.0), 1),
            "pre_latency": round(float(sleep_pre["eight_latency"] or 0.0), 1),
            "post_latency": round(float(sleep_post["eight_latency"] or 0.0), 1),
            "pre_breathing": round(float(sleep_pre["eight_breathing"] or 0.0), 3),
            "post_breathing": round(float(sleep_post["eight_breathing"] or 0.0), 3),
            "pre_snore_pct": round(float(sleep_pre["eight_snore_pct"] or 0.0), 1),
            "post_snore_pct": round(float(sleep_post["eight_snore_pct"] or 0.0), 1),
            "pre_spo2": round(float(sleep_pre["whoop_spo2"] or 0.0), 1),
            "post_spo2": round(float(sleep_post["whoop_spo2"] or 0.0), 1),
        },
        "training_180d": {
            "days": int(training_180["days"]),
            "avg_strain": round(float(training_180["avg_strain"] or 0.0), 2),
            "avg_recovery": round(float(training_180["avg_recovery"] or 0.0), 1),
            "avg_hrv": round(float(training_180["avg_hrv"] or 0.0), 1),
            "avg_rhr": round(float(training_180["avg_rhr"] or 0.0), 1),
            "avg_sleep_h": round(float(training_180["avg_sleep_h"] or 0.0), 2),
            "avg_sleep_perf": round(float(training_180["avg_sleep_perf"] or 0.0), 1),
            "high_strain_share": round(high_strain_share, 3),
            "very_high_strain_share": round(very_high_strain_share, 3),
        },
        "latest_lab_date": latest_lab_date,
        "body_comp_latest": (
            None
            if latest_body_comp is None
            else {
                "date": latest_body_comp["date"],
                "weight_kg": latest_body_comp["weight_kg"],
                "body_fat_pct": latest_body_comp["body_fat_pct"],
                "muscle_mass_kg": latest_body_comp["muscle_mass_kg"],
                "source": latest_body_comp["source"],
            }
        ),
        "body_comp_180d": {
            "days": int(body_comp_180["days"]),
            "avg_weight_kg": (
                None
                if body_comp_180["avg_weight_kg"] is None
                else round(float(body_comp_180["avg_weight_kg"]), 1)
            ),
            "avg_body_fat_pct": (
                None
                if body_comp_180["avg_body_fat_pct"] is None
                else round(float(body_comp_180["avg_body_fat_pct"]), 1)
            ),
            "avg_muscle_mass_kg": (
                None
                if body_comp_180["avg_muscle_mass_kg"] is None
                else round(float(body_comp_180["avg_muscle_mass_kg"]), 1)
            ),
        },
        "labs": {
            "LDL": labs.get("LDL"),
            "HDL": labs.get("HDL"),
            "Triglycerides": labs.get("Triglycerides"),
            "HbA1c": labs.get("HbA1c"),
            "Glucose": labs.get("Glucose"),
            "Vitamin D": labs.get("Vitamin D"),
            "TSH": labs.get("TSH"),
            "eGFR": labs.get("eGFR"),
            "Creatinine": labs.get("Creatinine"),
        },
        "derived": {
            "combined_sleep_h_90d": round(combined_sleep, 2),
            "sleep_need": round(sleep_need, 3),
            "recovery_gap": round(recovery_gap, 3),
            "sleep_quality_gap": round(sleep_quality_gap, 3),
            "waso_gap": round(waso_gap, 3),
            "sleep_burden_annual_qaly": round(sleep_burden_annual_qaly, 5),
            "sleep_component_burdens": {
                key: round(value, 3) for key, value in sleep_estimate.component_burdens.items()
            },
            "sleep_component_losses": {
                key: round(value, 5) for key, value in sleep_estimate.component_losses.items()
            },
            "sleep_component_utility_weight_ids": dict(
                sleep_estimate.component_utility_weight_ids
            ),
            "sleep_component_utility_lineage": sleep_utility_lineage(sleep_estimate),
            "sleep_mortality_signal": round(sleep_estimate.mortality_signal, 3),
            "airway_response_signal": round(airway_response_signal, 3),
            "sleep_study": {
                "date": "2026-03-25",
                "type": context.home_sleep_study.study_type,
                "rei": context.home_sleep_study.rei,
                "mean_spo2": context.home_sleep_study.mean_spo2,
                "nadir_spo2": context.home_sleep_study.nadir_spo2,
                "obstructive_apneas": context.home_sleep_study.obstructive_apneas,
                "hypopneas": context.home_sleep_study.hypopneas,
                "supine_fraction": context.home_sleep_study.supine_fraction,
                "supine_rei": context.home_sleep_study.supine_rei,
                "used_nasal_steroid": context.home_sleep_study.used_nasal_steroid,
                "used_nasal_strips": context.home_sleep_study.used_nasal_strips,
            },
            "sleep_airway": {
                "upper_airway_probability": round(
                    float(sleep_estimate.airway.upper_airway_probability) if sleep_estimate.airway else 0.0,
                    3,
                ),
                "nasal_inflammation_probability": round(
                    float(sleep_estimate.airway.nasal_inflammation_probability) if sleep_estimate.airway else 0.0,
                    3,
                ),
                "mucus_probability": round(
                    float(sleep_estimate.airway.mucus_probability) if sleep_estimate.airway else 0.0,
                    3,
                ),
            },
            "cardio_need": round(cardio_need, 3),
            "structured_intensity_headroom": round(structured_intensity_headroom, 3),
            "fitness_signal": round(fitness_signal, 3),
            "hiit_headroom": round(hiit_headroom, 3),
            "vitamin_d_need": round(vitamin_d_need, 3),
            "kidney_caution": round(kidney_caution, 3),
        },
    }


def build_specs(
    baseline: dict[str, Any],
    context: ProtocolContext | None = None,
) -> dict[str, StackSpec]:
    context = resolve_protocol_context(context)
    sleep_need = baseline["derived"]["sleep_need"]
    cardio_need = baseline["derived"]["cardio_need"]
    vitamin_d_need = baseline["derived"]["vitamin_d_need"]
    kidney_caution = baseline["derived"]["kidney_caution"]

    sleep_multiplier = 0.75 + 0.5 * sleep_need
    cardio_multiplier = 0.20 + 0.80 * cardio_need
    vitamin_d_multiplier = 0.05 + 0.95 * vitamin_d_need
    longevity_multiplier = 0.25
    eye_multiplier = 0.20
    joint_multiplier = 0.30
    fatigue_multiplier = 0.45
    exercise_multiplier = 0.55
    kidney_safe_multiplier = 1.0 - 0.25 * kidney_caution
    age = context.profile.age
    activity_level = context.profile.activity_level

    return {
        "tadalafil_2.5mg": StackSpec(
            item_id="tadalafil_2.5mg",
            observed_hr=math.exp(math.log(0.90) * cardio_multiplier),
            log_sd=0.10,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0032,
            qol_years=15,
            general_qol_utility_weight_ids=SEXUAL_FUNCTION_QOL,
            general_qol_lineage_note=(
                "Low-dose tadalafil's modeled utility is a small fraction of the published "
                "time-tradeoff utility gain for treating erectile dysfunction."
            ),
            low_qaly=0.02,
            high_qaly=0.09,
            personalization=(
                "Kept meaningful on QOL because current use reveals real private value, but "
                "the mortality side is heavily shrunk because PDE5 survival data are mostly "
                "observational in older, higher-risk men."
            ),
            rationale=(
                "Tadalafil probably matters more through sexual-function / wellbeing utility than "
                "through proven life-extension at your baseline risk."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/38777751/",
                "https://pubmed.ncbi.nlm.nih.gov/34775577/",
            ),
        ),
        "finasteride_1.25mg": StackSpec(
            item_id="finasteride_1.25mg",
            observed_hr=1.0,
            log_sd=0.03,
            conf_alpha=1.0,
            conf_beta=8.0,
            qol_annual=0.0024,
            qol_years=15,
            general_qol_utility_weight_ids=HAIR_QOL,
            general_qol_lineage_note=(
                "Hair-preservation utility is mapped from mild alopecia health-state utilities; "
                "the source is alopecia areata rather than androgenetic alopecia."
            ),
            low_qaly=-0.01,
            high_qaly=0.06,
            personalization=(
                "Modeled almost entirely as QOL: hair preservation seems clearly valued, but I netted "
                "that against sexual-side-effect risk rather than assuming pure upside."
            ),
            rationale=(
                "Hair-loss treatment has meaningful psychosocial value for some men, but very little "
                "credible mortality effect."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/21806672/",
                "https://pubmed.ncbi.nlm.nih.gov/37605428/",
                "https://pubmed.ncbi.nlm.nih.gov/28396101/",
            ),
        ),
        "magnesium_200": StackSpec(
            item_id="magnesium_200",
            observed_hr=math.exp(math.log(0.96) * cardio_multiplier),
            log_sd=0.08,
            conf_alpha=2.8,
            conf_beta=4.0,
            qol_annual=0.0018 * sleep_multiplier,
            qol_years=12,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual hand-estimated utility is anchored to insomnia/anxiety disability "
                "weights; component sleep relief is modeled separately."
            ),
            sleep_component_relief={
                "duration": 0.08,
                "quality": 0.20,
                "daytime": 0.15,
            },
            low_qaly=0.01,
            high_qaly=0.05,
            personalization=(
                f"Upweighted because your 90-day combined sleep is only {baseline['derived']['combined_sleep_h_90d']} h/night; "
                "small BP benefit remains because magnesium RCTs are stronger than most supplements."
            ),
            rationale=(
                "At your baseline, magnesium looks more like a sleep-support and small BP intervention "
                "than a major longevity lever."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/33865376/",
                "https://pubmed.ncbi.nlm.nih.gov/41000008/",
                "https://pubmed.ncbi.nlm.nih.gov/27402922/",
            ),
        ),
        "trazodone_50mg": StackSpec(
            item_id="trazodone_50mg",
            log_sd=0.06,
            conf_alpha=1.5,
            conf_beta=6.0,
            qol_annual=0.0030 * sleep_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual symptom utility is anchored to insomnia/anxiety disability weights; "
                "sedation harms and component sleep relief are modeled separately."
            ),
            low_qaly=-0.01,
            high_qaly=0.06,
            personalization=(
                "Upweighted because sleep is still clearly below target, but netted against hangover / "
                "dependency / long-run medication burden rather than assuming all sleep-med utility is durable."
            ),
            rationale=(
                "Trazodone looks like a symptomatic sleep/QOL tool here, not a credible mortality intervention."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/36216367/",
                "https://pubmed.ncbi.nlm.nih.gov/22208861/",
                "https://pubmed.ncbi.nlm.nih.gov/41209816/",
            ),
        ),
        "melatonin_300mcg": StackSpec(
            item_id="melatonin_300mcg",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.7,
            conf_beta=5.5,
            qol_annual=0.0014 * sleep_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual symptom utility is anchored to insomnia/anxiety disability weights; "
                "component sleep relief is modeled separately."
            ),
            low_qaly=-0.01,
            high_qaly=0.03,
            personalization=(
                "Upweighted because short sleep is a live issue, but kept modest because human meta-analytic effects "
                "are measured in minutes, not hours."
            ),
            rationale=(
                "Small, probably real sleep-onset benefit; unlikely to be a big standalone QALY driver."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/15649737/",
                "https://pubmed.ncbi.nlm.nih.gov/22208861/",
            ),
        ),
        "nasacort_nightly": StackSpec(
            item_id="nasacort_nightly",
            qol_annual=0.0002,
            qol_years=10,
            general_qol_utility_weight_ids=AIRWAY_SLEEP_QOL,
            general_qol_lineage_note=(
                "Small residual nasal-comfort utility is anchored to sleep-apnoea/insomnia "
                "fallback weights; component sleep-breathing relief is modeled separately."
            ),
            low_qaly=-0.01,
            high_qaly=0.06,
            personalization=(
                "Upweighted because your recent airway-directed trial improved breathing, latency, snoring, and sleep quality, "
                f"producing an airway-response signal of {baseline['derived']['airway_response_signal']}."
            ),
            rationale=(
                "Nasacort looks like a phenotype-specific sleep intervention here: worthwhile if nasal inflammation or congestion "
                "is meaningfully contributing, not a generic prevention supplement."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/9042068/",
                "https://pubmed.ncbi.nlm.nih.gov/15124166/",
            ),
        ),
        "nasal_strips_nightly": StackSpec(
            item_id="nasal_strips_nightly",
            qol_annual=0.0001,
            qol_years=10,
            general_qol_utility_weight_ids=AIRWAY_SLEEP_QOL,
            general_qol_lineage_note=(
                "Small residual nasal-comfort utility is anchored to sleep-apnoea/insomnia "
                "fallback weights; component sleep-breathing relief is modeled separately."
            ),
            low_qaly=0.0,
            high_qaly=0.03,
            personalization=(
                "Upweighted because your own notes say the first night with strips plus Nasacort gave zero snoring, "
                "but kept smaller than Nasacort because the evidence is mostly subjective-sleep benefit."
            ),
            rationale=(
                "Nasal strips can help if upper-airway narrowing is part of the problem, but they are usually an adjunct rather than a decisive treatment."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/30154874/",
            ),
        ),
        "humidifier_nightly": StackSpec(
            item_id="humidifier_nightly",
            qol_annual=0.00005,
            qol_years=10,
            general_qol_utility_weight_ids=AIRWAY_SLEEP_QOL,
            general_qol_lineage_note=(
                "Fallback proxy for nasal-airway comfort; this is not a formal nasal-dryness "
                "utility source."
            ),
            low_qaly=0.0,
            high_qaly=0.01,
            personalization=(
                "Kept small because your current evidence points more to upper-airway obstruction and nasal inflammation "
                f"than to dry-air irritation alone; nasal-inflammation probability is {baseline['derived']['sleep_airway']['nasal_inflammation_probability']}."
            ),
            rationale=(
                "A bedroom humidifier is modeled as a modest nasal-comfort adjunct, not a real OSA treatment. "
                "It is most attractive when the room is actually dry or you wake with dry irritated nasal passages."
            ),
            sources=(
                "https://www.aaaai.org/tools-for-the-public/conditions-library/allergies/humidifiers-and-indoor-allergies",
                "https://www.epa.gov/mold/mold-course-chapter-2",
                "https://pubmed.ncbi.nlm.nih.gov/3348500/",
            ),
        ),
        "mouth_tape_nightly": StackSpec(
            item_id="mouth_tape_nightly",
            qol_annual=0.00008,
            qol_years=10,
            general_qol_utility_weight_ids=AIRWAY_SLEEP_QOL,
            general_qol_lineage_note=(
                "Small residual mouth-breathing comfort utility is anchored to sleep-apnoea/"
                "insomnia fallback weights."
            ),
            low_qaly=-0.002,
            high_qaly=0.03,
            personalization=(
                "Upweighted because you now have confirmed mild OSA plus a strong recent airway-response pattern, "
                "but kept below strips and head elevation because mouth tape only really makes sense if mouth breathing "
                f"is part of the phenotype and your data still point heavily to nasal and upper-airway contributors; upper-airway probability is {baseline['derived']['sleep_airway']['upper_airway_probability']}."
            ),
            rationale=(
                "Mouth tape is modeled as a plausible adjunct if habitual open-mouth breathing is part of the problem, "
                "not as a broad OSA treatment. The direct evidence is small and mostly in mild OSA or snoring."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/25450408/",
                "https://pubmed.ncbi.nlm.nih.gov/38780959/",
                "https://pubmed.ncbi.nlm.nih.gov/39662104/",
                "https://pubmed.ncbi.nlm.nih.gov/25766699/",
            ),
        ),
        "head_elevation_nightly": StackSpec(
            item_id="head_elevation_nightly",
            conf_alpha=2.1,
            conf_beta=4.4,
            qol_annual=0.0001,
            qol_years=10,
            general_qol_utility_weight_ids=AIRWAY_SLEEP_QOL,
            general_qol_lineage_note=(
                "Small residual positional-comfort utility is anchored to sleep-apnoea/"
                "insomnia fallback weights."
            ),
            low_qaly=0.0,
            high_qaly=0.04,
            personalization=(
                "Upweighted because your recent improvement pattern is compatible with an upper-airway contributor, but kept modest because your home data do not cleanly isolate elevation from the other airway changes."
            ),
            rationale=(
                "Head elevation is a low-risk positional airway aid with the best case in upper-airway-predominant sleep-disordered breathing."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/39347559/",
            ),
        ),
        "cocoa_flavanols_500": StackSpec(
            item_id="cocoa_flavanols_500",
            observed_hr=math.exp(math.log(0.95) * cardio_multiplier),
            log_sd=0.09,
            conf_alpha=2.5,
            conf_beta=4.5,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=0.0,
            high_qaly=0.03,
            personalization=(
                "Downweighted because LDL and glycemia are already good and COSMOS enrolled much older adults."
            ),
            rationale=(
                "Some plausible cardiometabolic value, but your current risk profile leaves less headroom."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/35294962/",
            ),
        ),
        "creatine_5g": StackSpec(
            item_id="creatine_5g",
            observed_hr=1.0,
            log_sd=0.04,
            conf_alpha=2.0,
            conf_beta=5.0,
            qol_annual=0.0014 * exercise_multiplier * kidney_safe_multiplier,
            qol_years=15,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Functional/performance utility is anchored to a mild motor-impairment "
                "fallback weight; the modeled annual utility is intentionally much smaller."
            ),
            low_qaly=0.0,
            high_qaly=0.03,
            personalization=(
                "Kept positive for muscle/performance resilience, but trimmed because you are 39 rather than sarcopenic "
                "and because creatinine/eGFR make me avoid giving it a free pass."
            ),
            rationale=(
                "Creatine has decent functional evidence, but most of the compelling data are performance / body-composition "
                "and older-adult contexts rather than mortality."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/39074168/",
                "https://pubmed.ncbi.nlm.nih.gov/24576864/",
            ),
        ),
        "omega3_clo": StackSpec(
            item_id="omega3_clo",
            observed_hr=math.exp(math.log(0.97) * cardio_multiplier),
            log_sd=0.08,
            conf_alpha=3.2,
            conf_beta=4.2,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=0.0,
            high_qaly=0.015,
            personalization=(
                "Strongly downweighted because this is a low dose and your LDL/HbA1c are already favorable."
            ),
            rationale=(
                "The marginal benefit of low-dose cod liver oil looks small at your baseline risk."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/32722395/",
                "https://pubmed.ncbi.nlm.nih.gov/24638908/",
            ),
        ),
        "garlic_1200": StackSpec(
            item_id="garlic_1200",
            observed_hr=math.exp(math.log(0.95) * cardio_multiplier),
            log_sd=0.08,
            conf_alpha=2.8,
            conf_beta=4.2,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=0.0,
            high_qaly=0.03,
            personalization=(
                "Downweighted because garlic's BP signal is clearest in hypertensive adults and you are not documented hypertensive."
            ),
            rationale=(
                "Garlic is a plausible small cardiometabolic adjunct, not a major longevity mover for you."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/40735665/",
                "https://pubmed.ncbi.nlm.nih.gov/26764326/",
            ),
        ),
        "prebiotics": StackSpec(
            item_id="prebiotics",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.7,
            conf_beta=5.5,
            qol_annual=0.0008,
            qol_years=10,
            general_qol_utility_weight_ids=BOWEL_HABIT_QOL,
            general_qol_lineage_note=(
                "Gut-comfort utility is anchored to bowel-habit/IBS fallback disability weights."
            ),
            low_qaly=0.0,
            high_qaly=0.02,
            personalization=(
                "Modeled as a gut-symptom / bowel-habit item rather than a mortality lever."
            ),
            rationale=(
                "Prebiotics may help GI comfort or satiety, but human hard-endpoint evidence is weak."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/24230488/",
                "https://pubmed.ncbi.nlm.nih.gov/41233756/",
            ),
        ),
        "vitamin_d_2000": StackSpec(
            item_id="vitamin_d_2000",
            observed_hr=math.exp(math.log(0.94) * vitamin_d_multiplier),
            log_sd=0.08,
            conf_alpha=3.0,
            conf_beta=4.0,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=-0.02,
            high_qaly=0.005,
            personalization=(
                f"Almost fully downweighted because your latest 25(OH)D is {baseline['labs']['Vitamin D']} ng/mL, already in a replete range."
            ),
            rationale=(
                "Vitamin D looks more like a deficiency correction tool than an additional-optimization tool at your current level."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/37004841/",
                "https://pubmed.ncbi.nlm.nih.gov/28096125/",
            ),
        ),
        "astaxanthin_12": StackSpec(
            item_id="astaxanthin_12",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization=(
                "Kept near zero because the human literature is mostly biomarker and specialty-population work."
            ),
            rationale=(
                "Interesting antioxidant biomarker story, but weak evidence for durable clinical payoff in someone like you."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/41596351/",
                "https://pubmed.ncbi.nlm.nih.gov/41710469/",
            ),
        ),
        "nac_1200": StackSpec(
            item_id="nac_1200",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.4,
            conf_beta=5.8,
            qol_annual=0.0010 * fatigue_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Fatigue/functional-reserve utility is anchored to a mild motor-impairment "
                "fallback weight; airway sleep relief is modeled separately."
            ),
            sleep_component_relief={
                "breathing": 0.08,
                "quality": 0.02,
            },
            airway_target_weights={
                "mucus": 0.75,
                "upper_airway": 0.25,
            },
            low_qaly=0.0,
            high_qaly=0.015,
            personalization=(
                "Trimmed because your sleep pattern and recent response point more to an upper-airway/nasal issue than a mucus-heavy phenotype. "
                "NAC keeps some value for fatigue or secretions, but much less than airway-targeted measures."
            ),
            rationale=(
                "NAC remains speculative for broad prevention. Its respiratory upside is much more credible in chronic bronchitis or mucus-heavy phenotypes than in nasal-obstruction sleep problems."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/38555190/",
                "https://pubmed.ncbi.nlm.nih.gov/28122105/",
            ),
        ),
        "curcumin_250": StackSpec(
            item_id="curcumin_250",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.5,
            conf_beta=5.5,
            qol_annual=0.0008 * fatigue_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=JOINT_QOL,
            general_qol_lineage_note=(
                "Anti-inflammatory symptom utility is anchored to a mild musculoskeletal-pain "
                "fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.012,
            personalization=(
                "Kept small because dose is modest and the strongest human data are for biomarker shifts or disease-specific pain populations."
            ),
            rationale=(
                "Curcumin is better supported as an anti-inflammatory biomarker intervention than a proven longevity intervention."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/38945354/",
                "https://pubmed.ncbi.nlm.nih.gov/39478418/",
            ),
        ),
        "collagen_22g": apply_joint_fall_pathway(
            StackSpec(
                item_id="collagen_22g",
                observed_hr=1.0,
                log_sd=0.05,
                conf_alpha=1.8,
                conf_beta=5.0,
                qol_annual=0.0008 * joint_multiplier,
                qol_years=10,
                general_qol_utility_weight_ids=JOINT_QOL,
                general_qol_lineage_note=(
                    "Joint-comfort utility is anchored to a mild musculoskeletal-pain "
                    "fallback weight."
                ),
                low_qaly=0.0,
                high_qaly=0.01,
                personalization=(
                    "Strongly downweighted because the better human data are in osteoarthritis / meniscopathy, not healthy adults without documented joint disease."
                ),
                rationale=(
                    "Collagen may help joint or skin outcomes in the right phenotype, but your baseline does not scream high-yield collagen responder."
                ),
                sources=(
                    "https://pubmed.ncbi.nlm.nih.gov/39212129/",
                    "https://pubmed.ncbi.nlm.nih.gov/38218227/",
                    "https://pubmed.ncbi.nlm.nih.gov/37432180/",
                ),
            ),
            age=age,
            activity_level=activity_level,
            joint_multiplier=joint_multiplier,
        ),
        "lutein_zeaxanthin": StackSpec(
            item_id="lutein_zeaxanthin",
            observed_hr=1.0,
            log_sd=0.04,
            conf_alpha=2.4,
            conf_beta=4.5,
            qol_annual=0.0004 * eye_multiplier,
            qol_years=20,
            general_qol_utility_weight_ids=VISION_QOL,
            general_qol_lineage_note=(
                "Vision-preservation utility is anchored to a mild vision-impairment "
                "fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.008,
            personalization=(
                "Downweighted because AREDS2 is secondary prevention in older adults with existing AMD risk, not primary prevention for a 39-year-old."
            ),
            rationale=(
                "Reasonable eye-health hedge, but the extrapolation to you is thin."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/39025435/",
                "https://pubmed.ncbi.nlm.nih.gov/24638908/",
            ),
        ),
        "vitamin_k2": StackSpec(
            item_id="vitamin_k2",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=2.0,
            conf_beta=4.8,
            qol_annual=0.0,
            qol_years=20,
            low_qaly=0.0,
            high_qaly=0.008,
            personalization=(
                "Kept near zero because the more favorable fracture/BMD data are mostly in older postmenopausal populations."
            ),
            rationale=(
                "Vitamin K2 is a weak preventive bet at your age unless there is a clearer bone-risk story."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/35625785/",
                "https://pubmed.ncbi.nlm.nih.gov/36033779/",
            ),
        ),
        "ubiquinol_50": StackSpec(
            item_id="ubiquinol_50",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.8,
            conf_beta=5.2,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.01,
            personalization=(
                "Near zero because the strongest CoQ10 evidence is in heart failure, which is not your phenotype."
            ),
            rationale=(
                "CoQ10 can be useful in cardiac disease or statin myalgia, but that is not the main story here."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/39462324/",
                "https://pubmed.ncbi.nlm.nih.gov/35608922/",
            ),
        ),
        "ubiquinol_50_unbundled": StackSpec(
            item_id="ubiquinol_50_unbundled",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.8,
            conf_beta=5.2,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.01,
            personalization=(
                "Same small CoQ10 estimate as the bundled version; the standalone question is mostly about whether it is worth buying separately."
            ),
            rationale=(
                "Standalone ubiquinol should inherit the same weak phenotype-specific estimate as bundled ubiquinol."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/39462324/",
                "https://pubmed.ncbi.nlm.nih.gov/35608922/",
                "https://www.lifeextension.com/vitamins-supplements/item01425/super-ubiquinol-coq10-with-ppm-pyrroloquinoline-quinone",
            ),
        ),
        "nr_300": StackSpec(
            item_id="nr_300",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0009 * fatigue_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Fatigue/recovery utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.015,
            personalization=(
                "I kept a small positive here only because there is at least one recent long-COVID RCT signal, but in healthier adults the literature is mostly NAD+ biomarker movement without obvious clinical payoff."
            ),
            rationale=(
                "NR is still mostly a mechanistic bet, with a small possible symptom pathway for fatigue / recovery."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/41357333/",
                "https://pubmed.ncbi.nlm.nih.gov/29184669/",
                "https://pubmed.ncbi.nlm.nih.gov/32320006/",
            ),
        ),
        "nr_300_unbundled": StackSpec(
            item_id="nr_300_unbundled",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0009 * fatigue_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Fatigue/recovery utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.015,
            personalization=(
                "Same biology as bundled NR; the question here is whether it is worth buying as a standalone product."
            ),
            rationale=(
                "Standalone NR should inherit the same tiny clinical estimate as bundled NR, with cost deciding the verdict."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/41357333/",
                "https://pubmed.ncbi.nlm.nih.gov/29184669/",
                "https://pubmed.ncbi.nlm.nih.gov/32320006/",
                "https://www.truniagen.com/products/tru-niagen-300mg",
            ),
        ),
        "luteolin_100": StackSpec(
            item_id="luteolin_100",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.0,
            conf_beta=6.5,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization=(
                "Near zero because I could not justify a meaningful clinical effect from current human outcome data."
            ),
            rationale=(
                "Luteolin remains mostly a mechanistic / preclinical longevity ingredient."
            ),
            sources=(),
        ),
        "luteolin_100_unbundled": StackSpec(
            item_id="luteolin_100_unbundled",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.0,
            conf_beta=6.5,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization=(
                "Same near-zero estimate as bundled luteolin; useful mainly to compare whether buying it separately makes any sense."
            ),
            rationale=(
                "Standalone luteolin should inherit the same mechanistic-only estimate as bundled luteolin."
            ),
            sources=("https://doublewoodsupplements.com/products/luteolin",),
        ),
        "lithium_1mg_orotate": StackSpec(
            item_id="lithium_1mg_orotate",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.1,
            conf_beta=6.2,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization=(
                "Kept near zero because microdose lithium/orotate evidence is too thin to support a stronger estimate."
            ),
            rationale=(
                "Interesting hypothesis space, but not enough human intervention data for a large claim."
            ),
            sources=(),
        ),
        "hyaluronic_acid_120": apply_joint_fall_pathway(
            StackSpec(
                item_id="hyaluronic_acid_120",
                observed_hr=1.0,
                log_sd=0.05,
                conf_alpha=1.4,
                conf_beta=5.5,
                qol_annual=0.0006 * joint_multiplier,
                qol_years=10,
                general_qol_utility_weight_ids=JOINT_QOL,
                general_qol_lineage_note=(
                    "Joint-comfort utility is anchored to a mild musculoskeletal-pain "
                    "fallback weight."
                ),
                low_qaly=0.0,
                high_qaly=0.01,
                personalization=(
                    "Downweighted because oral HA benefits are mostly in chronic pain / joint-discomfort populations."
                ),
                rationale=(
                    "Oral hyaluronic acid may have symptom value, but it looks phenotype-specific."
                ),
                sources=(
                    "https://pubmed.ncbi.nlm.nih.gov/25415767/",
                    "https://pubmed.ncbi.nlm.nih.gov/41479667/",
                ),
            ),
            age=age,
            activity_level=activity_level,
            joint_multiplier=joint_multiplier,
        ),
        "broccoli_seed_200": StackSpec(
            item_id="broccoli_seed_200",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.008,
            personalization=(
                "Near zero because sulforaphane has mechanistic appeal but little direct hard-endpoint evidence in a healthy adult."
            ),
            rationale=(
                "Promising biology; still thin as a personalized QALY lever."
            ),
            sources=(),
        ),
        "spermidine_10": StackSpec(
            item_id="spermidine_10",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization=(
                "Near zero because the better human RCT found no memory benefit despite strong preclinical enthusiasm."
            ),
            rationale=(
                "Spermidine is still more of a longevity hypothesis than a demonstrated human benefit."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/35616942/",
            ),
        ),
        "fisetin_100_unbundled": StackSpec(
            item_id="fisetin_100_unbundled",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.0,
            conf_beta=6.8,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.01,
            high_qaly=0.02,
            personalization="Same skeptical estimate as bundled fisetin; standalone purchase is mostly a cost question.",
            rationale="There is still no strong human basis for a meaningful fisetin QALY claim.",
            sources=("https://doublewoodsupplements.com/products/fisetin",),
        ),
        "lycopene_15": StackSpec(
            item_id="lycopene_15",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.4,
            conf_beta=5.2,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization=(
                "Near zero because the cardiovascular literature is mainly observational and food-pattern confounding is hard to strip away."
            ),
            rationale=(
                "Lycopene may be fine, but I do not see a strong supplement-specific QALY signal."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/28318092/",
            ),
        ),
        "ginger_400": apply_joint_fall_pathway(
            StackSpec(
                item_id="ginger_400",
                observed_hr=1.0,
                log_sd=0.05,
                conf_alpha=1.5,
                conf_beta=5.0,
                qol_annual=0.0005 * joint_multiplier,
                qol_years=10,
                general_qol_utility_weight_ids=JOINT_QOL,
                general_qol_lineage_note=(
                    "Joint-comfort utility is anchored to a mild musculoskeletal-pain "
                    "fallback weight."
                ),
                low_qaly=0.0,
                high_qaly=0.01,
                personalization=(
                    "Small positive only because human data support biomarker improvements and some joint-pain benefit, but your baseline does not show an obvious inflammatory pain phenotype."
                ),
                rationale=(
                    "Ginger looks mildly helpful, but not transformative."
                ),
                sources=(
                    "https://pubmed.ncbi.nlm.nih.gov/41123858/",
                    "https://pubmed.ncbi.nlm.nih.gov/40732990/",
                ),
            ),
            age=age,
            activity_level=activity_level,
            joint_multiplier=joint_multiplier,
        ),
        "boron_3": StackSpec(
            item_id="boron_3",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.0,
            conf_beta=6.2,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization=(
                "Near zero because I could not justify a clinically meaningful human outcome effect here."
            ),
            rationale=(
                "Boron may matter for micronutrient biology, but not enough to give it a real QALY number beyond noise."
            ),
            sources=(),
        ),
        "fisetin_100": StackSpec(
            item_id="fisetin_100",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.0,
            conf_beta=6.5,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.002,
            high_qaly=0.005,
            personalization=(
                "Modeled as flat because fisetin is still largely a senolytic hypothesis in humans."
            ),
            rationale=(
                "Strong marketing and interesting biology, but not enough human evidence for a positive ground-up estimate."
            ),
            sources=(),
        ),
    }


def build_additional_specs(
    baseline: dict[str, Any],
    context: ProtocolContext | None = None,
) -> dict[str, StackSpec]:
    context = resolve_protocol_context(context)
    sleep_need = baseline["derived"]["sleep_need"]
    cardio_need = baseline["derived"]["cardio_need"]
    sleep_airway = baseline["derived"]["sleep_airway"]
    sleep_study = baseline["derived"].get("sleep_study") or {}
    hiit_headroom = baseline["derived"]["hiit_headroom"]
    training_180 = baseline.get("training_180d", {})
    stress_multiplier = 0.45 + 0.55 * sleep_need
    metabolic_multiplier = 0.10 + 0.35 * cardio_need
    semaglutide_spec = build_semaglutide_spec(baseline, context.profile)
    return {
        "statin_5mg": make_spec(
            "statin_5mg",
            observed_hr=math.exp(math.log(0.95) * (0.15 + 0.55 * cardio_need)),
            log_sd=0.08,
            conf_alpha=3.8,
            conf_beta=3.2,
            qol_annual=0.0,
            qol_years=20,
            low_qaly=-0.01,
            high_qaly=0.05,
            personalization="Strong causal class, but you already have LDL 64 and no documented ASCVD, so most trial effects shrink hard on transport.",
            rationale="Statins are one of the more credible preventive drug classes, but the marginal benefit for a lean 39-year-old with already-good lipids is much smaller than headline meta-analytic averages.",
            sources=("https://pubmed.ncbi.nlm.nih.gov/22607822/",),
        ),
        "metformin_500mg": make_spec(
            "metformin_500mg",
            observed_hr=math.exp(math.log(0.97) * metabolic_multiplier),
            log_sd=0.10,
            conf_alpha=2.0,
            conf_beta=5.5,
            qol_annual=0.0,
            qol_years=12,
            low_qaly=-0.01,
            high_qaly=0.02,
            personalization="Downweighted heavily because your glycemia is already good and most compelling outcome data are in diabetic or prediabetic populations.",
            rationale="Metformin is plausible as a modest metabolic-risk intervention, but not a big generic longevity lever for your phenotype.",
            sources=("https://pubmed.ncbi.nlm.nih.gov/28802803/",),
        ),
        "empagliflozin": make_spec(
            "empagliflozin",
            observed_hr=math.exp(math.log(0.98) * metabolic_multiplier),
            log_sd=0.10,
            conf_alpha=1.8,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.01,
            high_qaly=0.02,
            personalization="Transport is extremely weak here because the flagship benefits are in diabetes, heart failure, and CKD populations rather than a healthy lean 39-year-old.",
            rationale="SGLT2 inhibitors are clinically important in the right phenotype, but they should not look like a major longevity drug for you.",
            sources=("https://pubmed.ncbi.nlm.nih.gov/26378978/",),
        ),
        "aspirin_81mg": make_spec(
            "aspirin_81mg",
            observed_hr=math.exp(math.log(0.985) * (0.20 + 0.40 * cardio_need)),
            log_sd=0.08,
            conf_alpha=2.2,
            conf_beta=5.8,
            qol_annual=0.0,
            qol_years=12,
            low_qaly=-0.03,
            high_qaly=0.01,
            personalization="The bleeding downside transports better to you than the net-prevention upside, because you are young and low-risk rather than high-ASCVD.",
            rationale="Low-dose aspirin is now mostly a narrow-risk tool, not a generic prevention default.",
            sources=("https://pubmed.ncbi.nlm.nih.gov/30221597/",),
        ),
        "semaglutide": semaglutide_spec,
        "rapamycin_5mg_wk": make_spec(
            "rapamycin_5mg_wk",
            observed_hr=1.0,
            log_sd=0.12,
            conf_alpha=1.1,
            conf_beta=6.5,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.01,
            high_qaly=0.03,
            personalization="I am treating this mainly as an uncertain translational hypothesis, not a currently supported personal-health intervention.",
            rationale="Rapamycin remains interesting, but human longevity evidence is too incomplete for a large positive estimate.",
            sources=("https://pubmed.ncbi.nlm.nih.gov/35322235/",),
        ),
        "lithium_5mg": make_spec(
            "lithium_5mg",
            observed_hr=1.0,
            log_sd=0.07,
            conf_alpha=1.3,
            conf_beta=6.0,
            qol_annual=0.0002,
            qol_years=15,
            general_qol_utility_weight_ids=STRESS_QOL,
            general_qol_lineage_note=(
                "Mood-stability hedge utility is anchored to a mild-anxiety fallback disability weight."
            ),
            low_qaly=-0.015,
            high_qaly=0.015,
            personalization="Kept small because the low-dose human outcome case is still mostly ecological and indirect.",
            rationale="Interesting neuropsychiatric hedge, but still thin as a quantified longevity intervention.",
        ),
        "17a_estradiol": make_spec(
            "17a_estradiol",
            observed_hr=1.0,
            log_sd=0.10,
            conf_alpha=1.0,
            conf_beta=6.8,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.01,
            high_qaly=0.02,
            personalization="Near zero because this is still mostly mouse lifespan extrapolation.",
            rationale="No strong basis for a meaningful human QALY claim here yet.",
        ),
        "acarbose_50mg": make_spec(
            "acarbose_50mg",
            observed_hr=1.0,
            log_sd=0.08,
            conf_alpha=1.4,
            conf_beta=6.0,
            qol_annual=-0.0005,
            qol_years=10,
            general_qol_utility_weight_ids=GUT_QOL,
            general_qol_lineage_note=(
                "Negative utility is anchored to an IBS fallback disability weight for GI burden."
            ),
            low_qaly=-0.02,
            high_qaly=0.01,
            personalization="Modeled as mildly negative because GI burden transports better than lifespan-mouse optimism.",
            rationale="Acarbose is more likely to create hassle than durable value for your current phenotype.",
        ),
        "glycine_2g": make_spec(
            "glycine_2g",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.5,
            conf_beta=6.0,
            qol_annual=0.0010 * stress_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual calming utility is anchored to insomnia/anxiety disability weights; "
                "component sleep relief is modeled separately."
            ),
            sleep_component_relief={
                "duration": 0.06,
                "quality": 0.14,
                "daytime": 0.10,
            },
            low_qaly=-0.01,
            high_qaly=0.03,
            personalization="Upweighted because sleep remains an active problem, but the evidence is still mainly symptom-level and measured in modest changes.",
            rationale="Glycine looks like a plausible sleep/QOL helper rather than a major mortality intervention.",
            sources=("https://pubmed.ncbi.nlm.nih.gov/22529837/",),
        ),
        "apigenin_50": make_spec(
            "apigenin_50",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.2,
            conf_beta=6.3,
            qol_annual=0.0008 * stress_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=STRESS_QOL,
            general_qol_lineage_note=(
                "Calming utility is anchored to a mild-anxiety fallback disability weight."
            ),
            sleep_component_relief={
                "quality": 0.12,
                "daytime": 0.08,
            },
            low_qaly=-0.01,
            high_qaly=0.02,
            personalization="Kept positive only through plausible calming/sleep utility, not through a strong causal longevity claim.",
            rationale="Apigenin is a reasonable sleep-stack experiment, but not a proven life-extension tool.",
        ),
        "omega3_epa_2g": make_spec(
            "omega3_epa_2g",
            observed_hr=math.exp(math.log(0.97) * (0.25 + 0.60 * cardio_need)),
            log_sd=0.09,
            conf_alpha=2.5,
            conf_beta=4.5,
            qol_annual=0.0,
            qol_years=15,
            low_qaly=-0.002,
            high_qaly=0.02,
            personalization="Marginally more plausible than low-dose omega-3 because triglycerides are not perfect, but still sharply trimmed at your baseline risk.",
            rationale="Some cardiometabolic plausibility remains, but the incremental value over your existing health profile is modest.",
        ),
        "taurine_500_topup": make_spec(
            "taurine_500_topup",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.01,
            personalization="Very small because this is only a top-up on top of Longevity Mix, not a full taurine intervention.",
            rationale="The marginal increment from 1.5g to 2g should not look large.",
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/34039357/",
                "https://pubmed.ncbi.nlm.nih.gov/39796489/",
            ),
        ),
        "urolithin_a_500": make_spec(
            "urolithin_a_500",
            observed_hr=1.0,
            log_sd=0.07,
            conf_alpha=1.5,
            conf_beta=5.8,
            qol_annual=0.0003,
            qol_years=12,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Exercise-recovery utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.015,
            personalization="I kept a small functional upside for exercise recovery / mitochondria, but not enough to justify a major QALY number.",
            rationale="Urolithin A is plausible but still early and expensive.",
        ),
        "ergothioneine_5": make_spec(
            "ergothioneine_5",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.1,
            conf_beta=6.2,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.008,
            personalization="Near zero because most of the case is still observational and nutrient-status based.",
            rationale="Interesting biomarker story, weak supplement-level clinical story.",
        ),
        "quercetin_500": make_spec(
            "quercetin_500",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.3,
            conf_beta=5.8,
            qol_annual=0.0003,
            qol_years=10,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Symptom/function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.012,
            personalization="Kept small because the best case is symptom relief in inflammatory/viral-persistence settings, not generic prevention.",
            rationale="Quercetin might matter in the right symptom cluster, but not as a broad longevity capsule.",
        ),
        "sulforaphane_20_extra": make_spec(
            "sulforaphane_20_extra",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.01,
            personalization="Incremental-only because you already get some sulforaphane exposure from food and the bundled broccoli seed extract.",
            rationale="The extra dose is mostly mechanistic optimism.",
        ),
        "pterostilbene_50": make_spec(
            "pterostilbene_50",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.0,
            conf_beta=6.5,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.002,
            high_qaly=0.008,
            personalization="Near zero because this is still a resveratrol-family hypothesis, not a robust human outcome intervention.",
            rationale="Little reason to assign a meaningful QALY effect.",
        ),
        "egcg_400": make_spec(
            "egcg_400",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.01,
            high_qaly=0.01,
            personalization="Near zero or slightly negative because liver-risk transport is clearer than mortality benefit transport in a supplement user like you.",
            rationale="Green-tea epidemiology should not become a large EGCG-capsule claim.",
        ),
        "berberine_500": make_spec(
            "berberine_500",
            observed_hr=math.exp(math.log(0.98) * metabolic_multiplier),
            log_sd=0.08,
            conf_alpha=1.6,
            conf_beta=5.8,
            qol_annual=-0.0005,
            qol_years=10,
            general_qol_utility_weight_ids=GUT_QOL,
            general_qol_lineage_note=(
                "Negative utility is anchored to an IBS fallback disability weight for GI burden."
            ),
            low_qaly=-0.02,
            high_qaly=0.01,
            personalization="Your glycemia is already good, so the GI downside matters more than the diabetes-trial upside.",
            rationale="Berberine is not an attractive personal intervention at your baseline.",
        ),
        "alpha_lipoic_acid_300": make_spec(
            "alpha_lipoic_acid_300",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.008,
            personalization="Near zero because the best-supported use case is diabetic neuropathy, not your phenotype.",
            rationale="Weak general-prevention case.",
        ),
        "pqq_20": make_spec(
            "pqq_20",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.1,
            conf_beta=6.2,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.008,
            personalization="Mostly a mitochondrial-biomarker bet with little direct human utility evidence.",
            rationale="Should be near zero unless future evidence improves materially.",
        ),
        "tmg_1g": make_spec(
            "tmg_1g",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.1,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.005,
            personalization="Tiny because this is mostly a methylation-support adjunct, not a clinically demonstrated intervention.",
            rationale="Hard to justify more than noise-level utility.",
        ),
        "ashwagandha_600": make_spec(
            "ashwagandha_600",
            observed_hr=1.0,
            log_sd=0.07,
            conf_alpha=1.8,
            conf_beta=5.5,
            qol_annual=0.0012 * stress_multiplier,
            qol_years=10,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Stress/sleep utility is anchored to insomnia/anxiety disability weights; "
                "component sleep relief is modeled separately."
            ),
            sleep_component_relief={
                "duration": 0.05,
                "quality": 0.12,
                "daytime": 0.12,
            },
            low_qaly=-0.015,
            high_qaly=0.04,
            personalization="This is one of the few candidates I’d keep meaningfully positive because your sleep/stress profile leaves room for symptomatic benefit.",
            rationale="Ashwagandha is best modeled as a stress/sleep/QOL intervention with non-zero rare downside.",
        ),
        "lions_mane_1g": make_spec(
            "lions_mane_1g",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.3,
            conf_beta=6.0,
            qol_annual=0.0006,
            qol_years=15,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Cognition/function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.015,
            personalization="Small only: human evidence is mainly cognition/mood signal, not durable prevention.",
            rationale="Lion’s Mane is plausible as a small cognitive/QOL bet, not a large life-extension lever.",
        ),
        "black_seed_oil_1g": make_spec(
            "black_seed_oil_1g",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.01,
            personalization="Kept near zero because evidence remains mostly biomarker and specialty-population work.",
            rationale="Interesting anti-inflammatory profile, weak quantified personal-health case.",
        ),
        "cistanche_200": make_spec(
            "cistanche_200",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.3,
            conf_beta=6.0,
            qol_annual=0.00075,
            qol_years=15,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Performance/recovery utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.02,
            personalization="Small positive through possible exercise/recovery utility, not because I trust a direct longevity story.",
            rationale="Cistanche is a plausible functional-performance bet with weak hard-outcome evidence.",
        ),
        "nmn_500": make_spec(
            "nmn_500",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.0,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.008,
            personalization="Near zero because NR/NMN remain mostly NAD-biomarker interventions in humans.",
            rationale="Mechanistic appeal is stronger than demonstrated clinical value.",
        ),
        "ghk_cu": make_spec(
            "ghk_cu",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.1,
            conf_beta=6.2,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=0.0,
            high_qaly=0.01,
            personalization="Modeled as flat because aesthetic/skin appearance utility is not currently represented in the public-health QALY reference case.",
            rationale="Topical GHK-Cu may help skin appearance, but I am not assigning generic healthspan QALYs without a mapped utility domain.",
        ),
        "vitamin_c_500_extra": make_spec(
            "vitamin_c_500_extra",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.3,
            conf_beta=5.8,
            qol_annual=0.0,
            qol_years=10,
            low_qaly=-0.002,
            high_qaly=0.005,
            personalization="Incremental vitamin C on top of adequate intake should be near flat.",
            rationale="No reason to expect much marginal benefit here.",
        ),
        "zinc_carnosine_75": make_spec(
            "zinc_carnosine_75",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.5,
            conf_beta=5.0,
            qol_annual=0.0002,
            qol_years=10,
            general_qol_utility_weight_ids=UPPER_GI_QOL,
            general_qol_lineage_note=(
                "Upper-GI symptom utility is anchored to a reflux fallback disability weight."
            ),
            low_qaly=0.0,
            high_qaly=0.006,
            personalization="Useful mainly if you have a real GI barrier/irritation problem; otherwise near zero.",
            rationale="Zinc carnosine is a phenotype-specific gut-symptom intervention, not a broad longevity tool.",
        ),
        "probiotic_daily": make_spec(
            "probiotic_daily",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.3,
            conf_beta=5.5,
            qol_annual=0.0004,
            qol_years=10,
            general_qol_utility_weight_ids=GUT_QOL,
            general_qol_lineage_note=(
                "Gut-comfort utility is anchored to an IBS fallback disability weight."
            ),
            low_qaly=-0.002,
            high_qaly=0.01,
            personalization=(
                "Downweighted because you do not have a strong documented GI indication, "
                "and you already run other gut-support items, so most of the plausible value here is small symptomatic upside."
            ),
            rationale=(
                "Daily probiotics are reasonable to test for GI comfort, but the broad long-run health case is weak "
                "and the marginal value on top of your existing gut stack should be small."
            ),
            sources=(
                "https://www.sportsresearch.store/products/probiotic-60-billion",
                "https://pubmed.ncbi.nlm.nih.gov/24230488/",
                "https://pubmed.ncbi.nlm.nih.gov/41233756/",
            ),
        ),
        "apap_nightly": make_spec(
            "apap_nightly",
            qol_annual=0.0002,
            qol_years=10,
            general_qol_utility_weight_ids=AIRWAY_SLEEP_QOL,
            general_qol_lineage_note=(
                "Residual mask/convenience-adjusted utility is anchored to sleep-apnoea/"
                "insomnia fallback weights; main sleep benefit is modeled separately."
            ),
            low_qaly=0.0,
            high_qaly=0.15,
            personalization=(
                f"Your March 25, 2026 home study showed mild OSA (REI {sleep_study.get('rei', 'n/a')}/hr), "
                f"and the updated airway probability is {sleep_airway['upper_airway_probability']}, so PAP now gets "
                "credit from an actual diagnosis rather than only wearable inference."
            ),
            rationale=(
                "With confirmed OSA, PAP is the most evidence-backed next sleep intervention by a wide margin."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/31806413/",
                "https://aasm.org/wp-content/uploads/2019/11/Treatment-OSA-with-PAP-Patient-Guide.pdf",
                "https://pubmed.ncbi.nlm.nih.gov/30736887/",
            ),
        ),
        "oral_appliance_custom": make_spec(
            "oral_appliance_custom",
            qol_annual=0.0002,
            qol_years=10,
            general_qol_utility_weight_ids=AIRWAY_SLEEP_QOL,
            general_qol_lineage_note=(
                "Residual appliance-convenience utility is anchored to sleep-apnoea/"
                "insomnia fallback weights; main sleep benefit is modeled separately."
            ),
            low_qaly=0.0,
            high_qaly=0.10,
            personalization=(
                f"Your home study is already in the nonsevere range (REI {sleep_study.get('rei', 'n/a')}/hr), so a custom oral appliance is now a concrete non-PAP option rather than a speculative backup."
            ),
            rationale=(
                "Custom oral appliance should usually underperform PAP on efficacy but can still be a credible option in mild OSA, especially if you prefer non-PAP treatment."
            ),
            sources=(
                "https://aasm.org/aasm-and-aadsm-issue-new-joint-clinical-practice-guideline-for-oral-appliance-therapy/",
                "https://pubmed.ncbi.nlm.nih.gov/26094920/",
                "https://pubmed.ncbi.nlm.nih.gov/32665778/",
            ),
        ),
        "doxepin_3mg": make_spec(
            "doxepin_3mg",
            qol_annual=0.0011 * stress_multiplier,
            qol_years=8,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual insomnia/stress utility is anchored to insomnia/anxiety disability "
                "weights; component sleep relief is modeled separately."
            ),
            low_qaly=-0.01,
            high_qaly=0.04,
            personalization=(
                "Modeled as a better-targeted sleep-maintenance bridge than trazodone, but still with some hangover and respiratory caution rather than assuming it is free upside."
            ),
            rationale=(
                "Low-dose doxepin has better insomnia-guideline support than trazodone for sleep maintenance, but it remains a symptom treatment rather than an airway fix."
            ),
            sources=(
                "https://aasm.org/resources/pdf/pharmacologictreatmentofinsomnia.pdf",
                "https://www.accessdata.fda.gov/drugsatfda_docs/label/2010/022036lbl.pdf",
            ),
        ),
        "daridorexant_25mg": make_spec(
            "daridorexant_25mg",
            qol_annual=0.0013 * stress_multiplier,
            qol_years=8,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual insomnia/stress utility is anchored to insomnia/anxiety disability "
                "weights; component sleep relief is modeled separately."
            ),
            low_qaly=-0.005,
            high_qaly=0.05,
            personalization=(
                "Modeled as the cleanest trazodone replacement candidate because it targets maintenance insomnia and has direct mild-to-moderate OSA respiratory-safety evidence, but its cost is brutal."
            ),
            rationale=(
                "Daridorexant looks like a more evidence-aligned insomnia alternative than trazodone in mild OSA, especially if you want less generic sedation."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/35065036/",
                "https://pubmed.ncbi.nlm.nih.gov/33305817/",
                "https://pubmed.ncbi.nlm.nih.gov/39543812/",
            ),
        ),
        "lemborexant_5mg": make_spec(
            "lemborexant_5mg",
            qol_annual=0.00145 * stress_multiplier,
            qol_years=8,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual insomnia/stress utility is anchored to insomnia/anxiety disability "
                "weights; component sleep relief is modeled separately."
            ),
            low_qaly=-0.005,
            high_qaly=0.055,
            personalization=(
                "Modeled as a strong maintenance-insomnia candidate with actual OSA respiratory-safety data, "
                "but probably a bit more next-day drag than daridorexant and likely not covered on your plan."
            ),
            rationale=(
                "Lemborexant looks like a credible evidence-based trazodone alternative in mild OSA, with stronger sleep-maintenance efficacy than doxepin "
                "and less respiratory discomfort than suvorexant."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/32585700/",
                "https://pubmed.ncbi.nlm.nih.gov/32187781/",
                "https://pubmed.ncbi.nlm.nih.gov/37677076/",
                "https://pubmed.ncbi.nlm.nih.gov/40848323/",
            ),
        ),
        "suvorexant_10mg": make_spec(
            "suvorexant_10mg",
            qol_annual=0.0012 * stress_multiplier,
            qol_years=8,
            general_qol_utility_weight_ids=SLEEP_RESIDUAL_QOL,
            general_qol_lineage_note=(
                "Residual insomnia/stress utility is anchored to insomnia/anxiety disability "
                "weights; component sleep relief is modeled separately."
            ),
            low_qaly=-0.008,
            high_qaly=0.045,
            personalization=(
                "Modeled as meaningfully better than trazodone on mechanism, but with more OSA-specific respiratory caution and next-day somnolence risk "
                "than daridorexant or lemborexant."
            ),
            rationale=(
                "Suvorexant is still a plausible maintenance-insomnia option, but the respiratory-safety story in OSA is less clean, "
                "so it ranks below the other DORAs for you."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/27397664/",
                "https://pubmed.ncbi.nlm.nih.gov/26194728/",
                "https://pubmed.ncbi.nlm.nih.gov/39543812/",
                "https://www.drugs.com/pro/belsomra.html",
            ),
        ),
        "hiit_1x_week": make_spec(
            "hiit_1x_week",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=2.0,
            conf_beta=4.8,
            qol_annual=0.0028 * hiit_headroom,
            qol_years=12,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Exercise-function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.04,
            personalization=(
                f"Your 180-day Whoop pattern shows avg strain {training_180.get('avg_strain', 0)} with "
                f"{round(100 * float(training_180.get('high_strain_share', 0.0)), 1)}% of days at >=14 strain, "
                f"so I model one structured interval session as a modest CRF upgrade rather than a big new training load."
            ),
            rationale=(
                "One weekly HIIT session looks like a plausible way to improve VO2max/cardiorespiratory fitness a bit without assuming sedentary-person returns."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/26243014/",
                "https://pubmed.ncbi.nlm.nih.gov/38599681/",
            ),
        ),
        "hiit_2x_week": make_spec(
            "hiit_2x_week",
            observed_hr=1.0,
            log_sd=0.07,
            conf_alpha=1.9,
            conf_beta=5.0,
            qol_annual=0.0045 * hiit_headroom,
            qol_years=12,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Exercise-function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.06,
            personalization=(
                "Two weekly interval sessions can add a bit more CRF upside, but the marginal return is still capped because you already train daily and your Whoop fitness proxies are strong."
            ),
            rationale=(
                "Two HIIT sessions per week is still plausible as a small positive, but only if it replaces easier cardio rather than stacking on top of everything."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/26243014/",
                "https://pubmed.ncbi.nlm.nih.gov/38599681/",
                "https://pubmed.ncbi.nlm.nih.gov/40976973/",
            ),
        ),
        "hiit_3x_week": make_spec(
            "hiit_3x_week",
            observed_hr=1.0,
            log_sd=0.08,
            conf_alpha=1.7,
            conf_beta=5.4,
            qol_annual=0.0038 * hiit_headroom - 0.0008 * (1.0 - sleep_need),
            qol_years=12,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Exercise-function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=-0.005,
            high_qaly=0.05,
            personalization=(
                "I allow a third interval session only as a near-flat extension of 2x/week, because your training load is already high and a 2025 frequency study found no clear extra benefit from 3x over 2x in recreational runners."
            ),
            rationale=(
                "Three HIIT sessions per week could be fine for some people, but for you I model it as roughly flat to slightly worse than 2x/week unless the extra stimulus clearly outperforms the recovery cost."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/26243014/",
                "https://pubmed.ncbi.nlm.nih.gov/38599681/",
                "https://pubmed.ncbi.nlm.nih.gov/40976973/",
            ),
        ),
        "zone2_cardio_2x_week": make_spec(
            "zone2_cardio_2x_week",
            observed_hr=1.0,
            log_sd=0.05,
            conf_alpha=1.8,
            conf_beta=5.0,
            qol_annual=0.0018 * hiit_headroom,
            qol_years=12,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Exercise-function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.025,
            personalization=(
                "Because you already run and train daily, I only give a small positive for making some cardio more intentionally aerobic and structured."
            ),
            rationale=(
                "Structured zone-2 work is still plausible as a small positive, but less likely than HIIT to create a meaningful new stimulus in your current routine."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/38599681/",
            ),
        ),
        "tempo_run_1x_week": make_spec(
            "tempo_run_1x_week",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.9,
            conf_beta=4.9,
            qol_annual=0.0034 * hiit_headroom,
            qol_years=12,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Exercise-function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.045,
            personalization=(
                "I place tempo work between zone 2 and HIIT: probably more additive than easy running, but not as distinct a VO2max stimulus as true intervals."
            ),
            rationale=(
                "A weekly tempo run is a credible middle-ground training intervention with modest expected upside."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/26243014/",
                "https://pubmed.ncbi.nlm.nih.gov/38599681/",
            ),
        ),
        "strength_maintenance": make_spec(
            "strength_maintenance",
            observed_hr=1.0,
            log_sd=0.04,
            conf_alpha=1.4,
            conf_beta=5.6,
            qol_annual=0.0003,
            qol_years=12,
            general_qol_utility_weight_ids=FUNCTION_QOL,
            general_qol_lineage_note=(
                "Strength/function utility is anchored to a mild motor-impairment fallback weight."
            ),
            low_qaly=0.0,
            high_qaly=0.01,
            personalization=(
                "Near flat because your described routine already contains daily strength work, so a separate strength-maintenance intervention adds little."
            ),
            rationale=(
                "Strength is important in general, but your marginal gain from formalizing it further appears small."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/38599681/",
            ),
        ),
        "traditional_sauna_4x_week": make_spec(
            "traditional_sauna_4x_week",
            observed_hr=1.0,
            log_sd=0.08,
            conf_alpha=1.8,
            conf_beta=4.8,
            qol_annual=0.0008,
            qol_years=15,
            general_qol_utility_weight_ids=STRESS_QOL + FUNCTION_QOL,
            general_qol_lineage_note=(
                "Relaxation/recovery utility is anchored to mild anxiety and functional "
                "impairment fallback weights."
            ),
            low_qaly=0.0,
            high_qaly=0.03,
            personalization=(
                "You already exercise daily and your cardiometabolic baseline is good, so I treat sauna as a modest relaxation/recovery and BP-surrogate intervention rather than as a real direct-longevity claim."
            ),
            rationale=(
                "Traditional dry sauna is the most plausible of the classic biohacker add-ons, but the credible benefit for you still looks modest."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/25705824/",
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC9394774/",
            ),
        ),
        "infrared_sauna_4x_week": make_spec(
            "infrared_sauna_4x_week",
            observed_hr=1.0,
            log_sd=0.07,
            conf_alpha=1.5,
            conf_beta=5.2,
            qol_annual=0.00035,
            qol_years=10,
            general_qol_utility_weight_ids=STRESS_QOL + FUNCTION_QOL,
            general_qol_lineage_note=(
                "Relaxation/recovery utility is anchored to mild anxiety and functional "
                "impairment fallback weights."
            ),
            low_qaly=0.0,
            high_qaly=0.015,
            personalization=(
                "I treat infrared sauna as a weaker recovery/relaxation analog to traditional dry sauna rather than as an equivalent longevity intervention."
            ),
            rationale=(
                "Infrared sauna may help relaxation or recovery a bit, but the evidence is materially weaker than for Finnish-style dry sauna."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/41049507/",
                "https://pmc.ncbi.nlm.nih.gov/articles/PMC9394774/",
            ),
        ),
        "hbot_60sessions": make_spec(
            "hbot_60sessions",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.2,
            conf_beta=6.4,
            qol_annual=0.0,
            qol_years=5,
            low_qaly=-0.01,
            high_qaly=0.01,
            personalization=(
                "I am treating HBOT as a high-cost surrogate-biomarker play with uncertain persistence, not as a demonstrated healthy-aging intervention."
            ),
            rationale=(
                "Interesting but weakly grounded for a healthy 39-year-old; the evidence does not justify a large QALY estimate."
            ),
            sources=(
                "https://pubmed.ncbi.nlm.nih.gov/35649312/",
                "https://www.fda.gov/medical-devices/letters-health-care-providers/follow-instructions-safe-use-hyperbaric-oxygen-therapy-devices-letter-health-care-providers",
            ),
        ),
        "bpc157_cycle": make_spec(
            "bpc157_cycle",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.0,
            conf_beta=6.8,
            qol_annual=0.0,
            qol_years=2,
            low_qaly=-0.01,
            high_qaly=0.005,
            personalization=(
                "Without a concrete injury or ulcer-healing phenotype, BPC-157 is mostly gray-market uncertainty and injection burden."
            ),
            rationale=(
                "For a healthy user, BPC-157 should be modeled as near-zero or slightly negative until real human efficacy and product-quality evidence improve."
            ),
            sources=(
                "https://index.mirasmart.com/AAOS2025/PDFfiles/AAOS2025-009087.PDF",
                "https://www.fda.gov/drugs/human-drug-compounding/understanding-risks-compounded-drugs",
            ),
        ),
        "tb500_cycle": make_spec(
            "tb500_cycle",
            observed_hr=1.0,
            log_sd=0.06,
            conf_alpha=1.0,
            conf_beta=7.0,
            qol_annual=0.0,
            qol_years=2,
            low_qaly=-0.012,
            high_qaly=0.004,
            personalization=(
                "This is even more speculative than BPC-157 in the absence of a specific recovery use case."
            ),
            rationale=(
                "TB-500 looks like a gray-market hypothesis stack component, not a credible general-health intervention."
            ),
            sources=(
                "https://www.fda.gov/drugs/human-drug-compounding/understanding-risks-compounded-drugs",
            ),
        ),
    }


def format_cost_per_qaly(item: dict[str, Any]) -> str:
    if item["total_qaly"] <= 0:
        return "net negative"
    if item["modeled_total_cost"] <= 0:
        return "dominant"
    cost_per = item["cost_per_qaly"]
    return "—" if cost_per is None else f"${cost_per:,}"


def render_ranking_table(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["_None._"]
    lines = [
        "| Item | Status | Type | Total QALY | Days | Cost | $/QALY | P(harm) |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in items:
        lines.append(
            f"| {item['name']} | {item['status']} | {item['display_category']} | "
            f"{item['total_qaly']:.4f} | {item['days']:.1f} | "
            f"${item['modeled_total_cost']:,.0f} | {format_cost_per_qaly(item)} | "
            f"{item['p_harm']:.1%} |"
        )
    return lines


def build_current_stack_drop_table(
    estimates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rank current-stack items by the modeled effect of dropping each one."""
    rows: list[dict[str, Any]] = []
    for item in estimates:
        if item.get("status") not in CURRENT_STACK_STATUSES:
            continue
        drop_qaly = -float(item["total_qaly"])
        rows.append({
            "id": item["id"],
            "name": item["name"],
            "status": item.get("status"),
            "display_category": item.get("display_category"),
            "annual_cost": item.get("annual_cost"),
            "modeled_total_cost": item.get("modeled_total_cost"),
            "continue_total_qaly": item["total_qaly"],
            "drop_qaly": round(drop_qaly, 4),
            "drop_days": round(drop_qaly * 365.25, 1),
            "p_drop_benefit": item["p_harm"],
            "continue_cost_per_qaly": item.get("cost_per_qaly"),
            "reference_case_status": item["reference_case_status"],
            "qaly_lineage_issues": list(item["qaly_lineage"]["issues"]),
        })
    rows.sort(key=lambda row: row["drop_qaly"], reverse=True)
    return rows


def format_continue_cost_per_qaly_for_drop(row: dict[str, Any]) -> str:
    if row["continue_total_qaly"] <= 0:
        return "net negative" if row["modeled_total_cost"] > 0 else "flat"
    if row["modeled_total_cost"] <= 0:
        return "free/bundled"
    cost_per = row["continue_cost_per_qaly"]
    return "—" if cost_per is None else f"${cost_per:,}"


def render_current_stack_drop_table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["_None._"]
    lines = [
        "| Item | Status | Drop ΔQALY | Drop days | Drop helps | Continue $/QALY | Lineage |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['status']} | {row['drop_qaly']:+.4f} | "
            f"{row['drop_days']:+.1f} | {row['p_drop_benefit']:.1%} | "
            f"{format_continue_cost_per_qaly_for_drop(row)} | "
            f"{row['reference_case_status']} |"
        )
    return lines


def simulate_structured_qaly(
    spec: StackSpec,
    item_id: str,
    sleep_estimate: SleepBurdenEstimate | None = None,
    profile: Profile | None = None,
    active_interaction_tags: tuple[str, ...] = (),
) -> dict[str, Any]:
    catalog_entry = CATALOG[item_id]
    resolved = resolve_stack_spec(spec, catalog_entry)
    active_profile = profile or PROFILE
    profile_effect_multiplier = (
        catalog_entry.profile_effect_multiplier(active_profile)
        if resolved.apply_profile_effect_rules
        else 1.0
    )
    adjusted_observed_hr = profile_adjusted_observed_hr(
        resolved.observed_hr,
        profile_effect_multiplier,
    )
    if abs(adjusted_observed_hr - 1.0) < 1e-12:
        hazard_ratio = Distribution(type="point", params={"value": 1.0})
    else:
        hazard_ratio = Distribution(
            type="lognormal",
            params={
                "hr": adjusted_observed_hr,
                "log_sd": resolved.log_sd,
            },
        )
    intervention = Intervention(
        id=resolved.item_id,
        name=resolved.item_id,
        category="medical",
        mortality=MortalityEffect(
            hazard_ratio=hazard_ratio
        ),
        harm_model=list(catalog_entry.harm_effects),
        interaction_tags=list(catalog_entry.interaction_tags),
        interaction_rules=list(catalog_entry.interaction_rules),
        confounding_prior=ConfoundingPrior(alpha=resolved.conf_alpha, beta=resolved.conf_beta),
    )
    scaled_sleep_relief = effective_sleep_component_relief(
        sleep_estimate,
        resolved.sleep_component_relief,
        resolved.airway_target_weights,
    )
    result, qaly_draws = simulate_qaly_profile_vectorized(
        intervention,
        active_profile,
        n_simulations=N_SIMULATIONS,
        discount_rate=QALY_DISCOUNT_RATE,
        baseline_hazard_multiplier=sleep_baseline_mortality_multiplier(sleep_estimate),
        global_intervention_hr_multiplier=sleep_intervention_mortality_hr_multiplier(
            sleep_estimate,
            scaled_sleep_relief,
        ),
        active_interaction_tags=active_interaction_tags,
        active_years=resolved.qol_years,
        random_state=stable_random_seed(item_id, "structured_qaly"),
        return_qaly_gains=True,
    )
    direct_harm_qaly = float(result.expected_harm_qalys + result.expected_interaction_harm_qalys)
    mortality_qaly = float(result.mean - direct_harm_qaly)
    return {
        "mortality_qaly": mortality_qaly,
        "direct_harm_qaly": direct_harm_qaly,
        "simulated_qaly": float(result.mean),
        "p_benefit": float(result.prob_positive),
        "p_harm": float(result.prob_negative),
        "qaly_draws": qaly_draws,
        "profile_effect_multiplier": profile_effect_multiplier,
        "effective_observed_hr": adjusted_observed_hr,
    }


def estimate_item(
    item: dict[str, Any],
    spec: StackSpec,
    baseline: dict[str, Any],
    context: ProtocolContext | None = None,
    active_interaction_tags: tuple[str, ...] = (),
    include_draws: bool = False,
) -> dict[str, Any]:
    context = resolve_protocol_context(context)
    resolved = resolve_stack_spec(spec, CATALOG[item["id"]])
    sleep_estimate = SleepBurdenEstimate(
        component_burdens={
            key: float(value)
            for key, value in baseline["derived"].get("sleep_component_burdens", {}).items()
        },
        component_losses={
            key: float(value)
            for key, value in baseline["derived"].get("sleep_component_losses", {}).items()
        },
        annual_qaly_loss=float(baseline["derived"].get("sleep_burden_annual_qaly", 0.0)),
        mortality_signal=float(baseline["derived"].get("sleep_mortality_signal", 0.0)),
        airway=None,
        component_utility_weight_ids={
            key: str(value)
            for key, value in (
                baseline["derived"].get("sleep_component_utility_weight_ids") or {}
            ).items()
        },
    )
    airway = baseline["derived"].get("sleep_airway") or {}
    if airway:
        sleep_estimate = SleepBurdenEstimate(
            component_burdens=sleep_estimate.component_burdens,
            component_losses=sleep_estimate.component_losses,
            annual_qaly_loss=sleep_estimate.annual_qaly_loss,
            mortality_signal=sleep_estimate.mortality_signal,
            airway=AirwayContributorEstimate(
                upper_airway_probability=float(airway.get("upper_airway_probability", 0.0)),
                nasal_inflammation_probability=float(airway.get("nasal_inflammation_probability", 0.0)),
                mucus_probability=float(airway.get("mucus_probability", 0.0)),
                response_signal=float(baseline["derived"].get("airway_response_signal", 0.0)),
            ),
            component_utility_weight_ids=sleep_estimate.component_utility_weight_ids,
        )
    simulated = simulate_structured_qaly(
        spec,
        item["id"],
        sleep_estimate=sleep_estimate,
        profile=context.profile,
        active_interaction_tags=active_interaction_tags,
    )
    mortality_qaly = simulated["mortality_qaly"]
    direct_harm_qaly = simulated["direct_harm_qaly"]
    general_qol_qaly = resolved.qol_annual * discount_factor(resolved.qol_years)
    scaled_sleep_relief = effective_sleep_component_relief(
        sleep_estimate,
        resolved.sleep_component_relief,
        resolved.airway_target_weights,
    )
    sleep_qol_annual = estimate_sleep_relief_annual_qaly(
        sleep_estimate,
        scaled_sleep_relief,
    )
    sleep_baseline_hazard_multiplier = sleep_baseline_mortality_multiplier(sleep_estimate)
    sleep_mortality_hr_multiplier = sleep_intervention_mortality_hr_multiplier(
        sleep_estimate,
        scaled_sleep_relief,
    )
    sleep_qol_qaly = sleep_qol_annual * discount_factor(resolved.qol_years)
    general_qol_draws = sample_qol_component_draws(
        general_qol_qaly,
        item_id=item["id"],
        component="general_qol",
        evidence_quality=CATALOG[item["id"]].evidence_quality,
    )
    sleep_qol_draws = sample_qol_component_draws(
        sleep_qol_qaly,
        item_id=item["id"],
        component="sleep_qol",
        evidence_quality=CATALOG[item["id"]].evidence_quality,
    )
    qol_qaly = float(np.mean(general_qol_draws + sleep_qol_draws))
    total_draws = simulated["qaly_draws"] + general_qol_draws + sleep_qol_draws
    total_qaly = float(np.mean(total_draws))
    p_benefit = float(np.mean(total_draws > 0))
    p_harm = float(np.mean(total_draws < 0))
    if p_benefit == 0.0 and p_harm == 0.0:
        p_benefit = p_harm = 0.5
    total_cost = modeled_total_cost(item.get("annual_cost"), resolved.qol_years)
    item_cost_per_qaly = cost_per_qaly(total_cost, total_qaly)
    qaly_lineage = qaly_lineage_payload(
        resolved=resolved,
        mortality_qaly=mortality_qaly,
        direct_harm_qaly=direct_harm_qaly,
        general_qol_qaly=general_qol_qaly,
        sleep_qol_qaly=sleep_qol_qaly,
        direct_harm_lineage=item_harm_utility_lineage(item["id"], active_interaction_tags),
        sleep_lineage=sleep_utility_lineage(sleep_estimate, scaled_sleep_relief),
    )

    estimate = {
        "id": item["id"],
        "name": item["name"],
        "status": item.get("status"),
        "category": item.get("category"),
        "display_category": item.get("display_category"),
        "annual_cost": item.get("annual_cost"),
        "modeled_total_cost": round(total_cost, 2),
        "cost_per_qaly": (
            None if item_cost_per_qaly is None else round(item_cost_per_qaly)
        ),
        "dose_notes": item.get("dose_notes"),
        "time_of_day": item.get("time_of_day"),
        "mortality_qaly": round(mortality_qaly, 4),
        "direct_harm_qaly": round(direct_harm_qaly, 4),
        "general_qol_qaly": round(general_qol_qaly, 4),
        "sleep_qol_qaly": round(sleep_qol_qaly, 4),
        "qol_qaly": round(qol_qaly, 4),
        "total_qaly": round(total_qaly, 4),
        "days": round(total_qaly * 365.25, 1),
        "p_benefit": round(p_benefit, 4),
        "p_harm": round(p_harm, 4),
        "range_low_qaly": resolved.low_qaly,
        "range_high_qaly": resolved.high_qaly,
        "within_range": resolved.low_qaly <= total_qaly <= resolved.high_qaly,
        "reference_case_status": qaly_lineage["overall_reference_case_status"],
        "qaly_lineage": qaly_lineage,
        "assumptions": {
            "observed_hr": resolved.observed_hr,
            "profile_effect_multiplier": round(simulated["profile_effect_multiplier"], 6),
            "apply_profile_effect_rules": resolved.apply_profile_effect_rules,
            "effective_observed_hr": round(simulated["effective_observed_hr"], 6),
            "genetic_rule_matches": matching_genetic_rule_rationales(
                CATALOG[item["id"]],
                context.profile,
            ),
            "log_sd": resolved.log_sd,
            "confounding_prior": {"alpha": resolved.conf_alpha, "beta": resolved.conf_beta},
            "qol_annual": round(resolved.qol_annual, 6),
            "sleep_qol_annual": round(sleep_qol_annual, 6),
            "sleep_baseline_hazard_multiplier": round(sleep_baseline_hazard_multiplier, 6),
            "sleep_mortality_hr_multiplier": round(sleep_mortality_hr_multiplier, 6),
            "sleep_component_relief": {
                key: round(value, 4) for key, value in scaled_sleep_relief.items()
            },
            "airway_target_weights": {
                key: round(value, 3) for key, value in resolved.airway_target_weights.items()
            },
            "qol_years": resolved.qol_years,
            "cost_years": resolved.qol_years,
            "qol_uncertainty_relative_sd": qol_uncertainty_relative_sd(
                CATALOG[item["id"]].evidence_quality,
            ),
        },
        "personalization": resolved.personalization,
        "rationale": resolved.rationale,
        "sources": list(resolved.sources),
    }
    if resolved.model_details is not None:
        estimate["assumptions"]["model_details"] = resolved.model_details
    if include_draws:
        estimate["_total_draws"] = total_draws
        estimate["_benefit_overlap_qaly"] = max(mortality_qaly, 0.0) + max(qol_qaly, 0.0)
    return estimate


def public_estimate_payload(estimate: dict[str, Any]) -> dict[str, Any]:
    """Drop internal Monte Carlo arrays before JSON serialization."""
    return {key: value for key, value in estimate.items() if not key.startswith("_")}


def active_state_item_ids(protocol_items: list[dict[str, Any]]) -> list[str]:
    """Return item ids that define the currently active protocol state."""
    return [
        str(item["id"])
        for item in protocol_items
        if str(item.get("status", "")) in CURRENT_STACK_STATUSES
    ]


def _ordered_state_ids(item_ids: list[str]) -> list[str]:
    """Stable unique state id list, preserving catalog/protocol order."""
    seen: set[str] = set()
    ordered: list[str] = []
    for item_id in item_ids:
        if item_id in seen:
            continue
        seen.add(item_id)
        ordered.append(item_id)
    return ordered


def _state_item_active_years(
    item_ids: list[str],
    specs: dict[str, StackSpec],
) -> dict[str, float]:
    years: dict[str, float] = {}
    for item_id in item_ids:
        if item_id not in specs or item_id not in CATALOG:
            continue
        years[item_id] = resolve_stack_spec(specs[item_id], CATALOG[item_id]).qol_years
    return years


def _state_item_qalys(
    item_ids: list[str],
    estimates_by_id: dict[str, dict[str, Any]],
) -> dict[str, float]:
    return {
        item_id: float(
            estimates_by_id[item_id].get(
                "_benefit_overlap_qaly",
                max(float(estimates_by_id[item_id].get("total_qaly", 0.0)), 0.0),
            )
        )
        for item_id in item_ids
        if item_id in estimates_by_id
    }


def evaluate_protocol_state(
    item_ids: list[str],
    estimates_by_id: dict[str, dict[str, Any]],
    specs: dict[str, StackSpec],
    context: ProtocolContext,
) -> dict[str, Any]:
    """Evaluate a full protocol state once, including shared stack effects."""
    state_ids = _ordered_state_ids(item_ids)
    draws = np.zeros(N_SIMULATIONS)
    total_cost = 0.0
    additive_qaly = 0.0
    for item_id in state_ids:
        estimate = estimates_by_id[item_id]
        draws += latent_protocol_item_draws(item_id, estimate)
        additive_qaly += float(estimate["total_qaly"])
        total_cost += float(estimate.get("modeled_total_cost") or 0.0)

    interaction_qaly, interaction_details = expected_stack_interaction_qaly(
        item_ids=state_ids,
        catalog_entries=CATALOG,
        profile=context.profile,
        qaly_discount_rate=QALY_DISCOUNT_RATE,
        item_active_years=_state_item_active_years(state_ids, specs),
        item_qalys=_state_item_qalys(state_ids, estimates_by_id),
    )
    state_draws = draws + interaction_qaly
    total_qaly = float(np.mean(state_draws))
    return {
        "item_ids": state_ids,
        "n_items": len(state_ids),
        "additive_qaly": round(additive_qaly, 4),
        "stack_interaction_qaly": round(interaction_qaly, 4),
        "total_qaly": round(total_qaly, 4),
        "total_days": round(total_qaly * 365.25, 1),
        "modeled_total_cost": round(total_cost, 2),
        "p_positive": round(float(np.mean(state_draws > 0)), 4),
        "interaction_details": interaction_details,
        "draw_model": "paired_latent_rank_copula",
        "_total_qaly_raw": total_qaly,
        "_modeled_total_cost_raw": total_cost,
        "_draws": state_draws,
    }


def marginal_cost_per_qaly(delta_cost: float, delta_qaly: float) -> int | None:
    if delta_qaly <= 0 or delta_cost <= 0:
        return None
    return round(delta_cost / delta_qaly)


def draw_correlation(a: np.ndarray, b: np.ndarray) -> float | None:
    if float(np.std(a)) <= 1e-12 or float(np.std(b)) <= 1e-12:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def format_marginal_cost_per_qaly(row: dict[str, Any]) -> str:
    if row["delta_qaly"] <= 0:
        return "net negative"
    if row["delta_cost"] < 0:
        return "dominant"
    if row["delta_cost"] == 0:
        return "free/bundled"
    cost_per = row.get("cost_per_qaly")
    return "—" if cost_per is None else f"${cost_per:,}"


def build_state_marginal_decision_table(
    protocol_items: list[dict[str, Any]],
    estimates_by_id: dict[str, dict[str, Any]],
    specs: dict[str, StackSpec],
    context: ProtocolContext,
) -> list[dict[str, Any]]:
    """Compute add/drop decisions as V(new full state) - V(current full state)."""
    current_ids = active_state_item_ids(protocol_items)
    current_state = evaluate_protocol_state(current_ids, estimates_by_id, specs, context)
    current_draws = current_state["_draws"]
    current_cost = float(current_state["modeled_total_cost"])

    rows: list[dict[str, Any]] = []
    for item in protocol_items:
        item_id = str(item["id"])
        status = str(item.get("status", ""))
        if status in CURRENT_STACK_STATUSES:
            action = "drop"
            new_ids = [state_id for state_id in current_ids if state_id != item_id]
        elif is_actionable_item(item):
            action = "add"
            new_ids = current_ids + [item_id]
        else:
            continue

        new_state = evaluate_protocol_state(new_ids, estimates_by_id, specs, context)
        new_draws = new_state["_draws"]
        delta_draws = new_draws - current_draws
        delta_qaly = float(np.mean(delta_draws))
        delta_cost = float(new_state["modeled_total_cost"]) - current_cost
        paired_state_correlation = draw_correlation(current_draws, new_draws)
        independent_delta_sd = math.sqrt(
            float(np.var(current_draws)) + float(np.var(new_draws)),
        )
        estimate = estimates_by_id[item_id]
        row = {
            "id": item_id,
            "name": estimate["name"],
            "action": action,
            "status": status,
            "display_category": estimate.get("display_category"),
            "standalone_total_qaly": estimate["total_qaly"],
            "delta_qaly": round(delta_qaly, 4),
            "delta_days": round(delta_qaly * 365.25, 1),
            "delta_sd": round(float(np.std(delta_draws)), 4),
            "independent_delta_sd": round(independent_delta_sd, 4),
            "paired_state_correlation": (
                None
                if paired_state_correlation is None
                else round(paired_state_correlation, 4)
            ),
            "delta_ci80": [
                round(float(np.percentile(delta_draws, 10)), 4),
                round(float(np.percentile(delta_draws, 90)), 4),
            ],
            "p_positive": round(float(np.mean(delta_draws > 0)), 4),
            "delta_cost": round(delta_cost, 2),
            "cost_per_qaly": marginal_cost_per_qaly(delta_cost, delta_qaly),
            "state_total_qaly_after": new_state["total_qaly"],
            "state_interaction_delta_qaly": round(
                float(new_state["stack_interaction_qaly"])
                - float(current_state["stack_interaction_qaly"]),
                4,
            ),
            "reference_case_status": estimate["reference_case_status"],
            "qaly_lineage_issues": list(estimate["qaly_lineage"]["issues"]),
        }
        if action == "drop":
            row.update({
                "continue_total_qaly": estimate["total_qaly"],
                "drop_qaly": row["delta_qaly"],
                "drop_days": row["delta_days"],
                "p_drop_benefit": row["p_positive"],
                "continue_cost_per_qaly": estimate.get("cost_per_qaly"),
                "modeled_total_cost": estimate.get("modeled_total_cost"),
            })
        rows.append(row)

    rows.sort(key=lambda row: row["delta_qaly"], reverse=True)
    return rows


def optimizable_protocol_item_ids(protocol_items: list[dict[str, Any]]) -> list[str]:
    """Return item ids the state optimizer may keep, add, or drop."""
    return _ordered_state_ids([
        str(item["id"])
        for item in protocol_items
        if (
            str(item.get("status", "")) in CURRENT_STACK_STATUSES
            or is_actionable_item(item)
        )
    ])


def exclusive_group_by_id(item_ids: list[str]) -> dict[str, str]:
    return {
        item_id: CATALOG[item_id].exclusive_group
        for item_id in item_ids
        if item_id in CATALOG and CATALOG[item_id].exclusive_group
    }


def feasible_protocol_state(
    item_ids: list[str],
    exclusive_groups: dict[str, str],
) -> list[str]:
    """Return a stable feasible state, keeping the first item in each group."""
    selected_groups: set[str] = set()
    feasible_ids: list[str] = []
    for item_id in _ordered_state_ids(item_ids):
        group = exclusive_groups.get(item_id)
        if group and group in selected_groups:
            continue
        if group:
            selected_groups.add(group)
        feasible_ids.append(item_id)
    return feasible_ids


def state_transition_actions(
    current_ids: list[str],
    target_ids: list[str],
) -> dict[str, list[str]]:
    current = set(current_ids)
    target = set(target_ids)
    added = sorted(target - current)
    dropped = sorted(current - target)
    swaps: list[str] = []
    for added_id in added:
        added_group = CATALOG.get(added_id).exclusive_group if added_id in CATALOG else None
        if not added_group:
            continue
        for dropped_id in dropped:
            dropped_group = (
                CATALOG.get(dropped_id).exclusive_group
                if dropped_id in CATALOG
                else None
            )
            if dropped_group == added_group:
                swaps.append(f"{dropped_id}->{added_id}")
    return {
        "add": added,
        "drop": dropped,
        "swap": swaps,
    }


def state_objective_value(
    state: dict[str, Any],
    objective: str,
    wtp: float,
) -> float:
    qaly = float(state.get("_total_qaly_raw", state["total_qaly"]))
    if objective == "qaly":
        return qaly
    if objective == "net_benefit":
        cost = float(state.get("_modeled_total_cost_raw", state["modeled_total_cost"]))
        return qaly * wtp - cost
    raise ValueError(f"Unknown optimizer objective: {objective}")


def protocol_state_cost(state: dict[str, Any]) -> float:
    return float(state.get("_modeled_total_cost_raw", state["modeled_total_cost"]))


def protocol_state_qaly(state: dict[str, Any]) -> float:
    return float(state.get("_total_qaly_raw", state["total_qaly"]))


def protocol_optimizer_neighbors(
    state_ids: list[str],
    universe_ids: list[str],
    exclusive_groups: dict[str, str],
) -> list[list[str]]:
    """Generate add/drop/swap neighbors for local full-state search."""
    selected = set(state_ids)
    neighbors: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def add_neighbor(candidate_ids: list[str]) -> None:
        feasible_ids = feasible_protocol_state(candidate_ids, exclusive_groups)
        key = tuple(feasible_ids)
        if key == tuple(state_ids) or key in seen:
            return
        seen.add(key)
        neighbors.append(feasible_ids)

    for item_id in state_ids:
        add_neighbor([selected_id for selected_id in state_ids if selected_id != item_id])

    for item_id in universe_ids:
        if item_id in selected:
            continue
        group = exclusive_groups.get(item_id)
        if group:
            conflicting_ids = [
                selected_id
                for selected_id in state_ids
                if exclusive_groups.get(selected_id) == group
            ]
            if conflicting_ids:
                add_neighbor([
                    selected_id
                    for selected_id in state_ids
                    if selected_id not in conflicting_ids
                ] + [item_id])
                continue
        add_neighbor(state_ids + [item_id])

    return neighbors


def build_optimizer_step(
    *,
    step: int,
    previous_ids: list[str],
    new_ids: list[str],
    previous_state: dict[str, Any],
    new_state: dict[str, Any],
    previous_objective_value: float,
    new_objective_value: float,
    objective: str,
    wtp: float,
    estimates_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    delta_draws = new_state["_draws"] - previous_state["_draws"]
    delta_qaly = float(np.mean(delta_draws))
    delta_cost = protocol_state_cost(new_state) - protocol_state_cost(previous_state)
    actions = state_transition_actions(previous_ids, new_ids)
    return {
        "step": step,
        "objective": objective,
        "actions": actions,
        "add_names": [estimates_by_id[item_id]["name"] for item_id in actions["add"]],
        "drop_names": [estimates_by_id[item_id]["name"] for item_id in actions["drop"]],
        "delta_qaly": round(delta_qaly, 4),
        "delta_days": round(delta_qaly * 365.25, 1),
        "p_positive": round(float(np.mean(delta_draws > 0)), 4),
        "delta_cost": round(delta_cost, 2),
        "cost_per_qaly": marginal_cost_per_qaly(delta_cost, delta_qaly),
        "delta_net_benefit": round(delta_qaly * wtp - delta_cost, 2),
        "delta_objective_value": (
            round(new_objective_value - previous_objective_value, 2)
            if objective == "net_benefit"
            else round(new_objective_value - previous_objective_value, 4)
        ),
        "state_total_qaly": new_state["total_qaly"],
        "state_total_days": new_state["total_days"],
        "state_total_cost": new_state["modeled_total_cost"],
        "state_objective_value": (
            round(new_objective_value, 2)
            if objective == "net_benefit"
            else round(new_objective_value, 4)
        ),
        "delta_ci80": [
            round(float(np.percentile(delta_draws, 10)), 4),
            round(float(np.percentile(delta_draws, 90)), 4),
        ],
        "paired_state_correlation": (
            None
            if draw_correlation(previous_state["_draws"], new_state["_draws"]) is None
            else round(float(draw_correlation(previous_state["_draws"], new_state["_draws"])), 4)
        ),
    }


def optimize_protocol_state(
    protocol_items: list[dict[str, Any]],
    estimates_by_id: dict[str, dict[str, Any]],
    specs: dict[str, StackSpec],
    context: ProtocolContext,
    *,
    objective: str = "net_benefit",
    wtp: float = PROTOCOL_OPTIMIZER_WTP,
    max_steps: int = PROTOCOL_OPTIMIZER_MAX_STEPS,
    min_improvement: float = PROTOCOL_OPTIMIZER_MIN_IMPROVEMENT,
) -> dict[str, Any]:
    """Greedy local search over full protocol states with exclusivity constraints."""
    universe_ids = optimizable_protocol_item_ids(protocol_items)
    exclusive_groups = exclusive_group_by_id(universe_ids)
    initial_ids = feasible_protocol_state(active_state_item_ids(protocol_items), exclusive_groups)
    state_cache: dict[tuple[str, ...], dict[str, Any]] = {}

    def evaluate_ids(item_ids: list[str]) -> dict[str, Any]:
        key = tuple(item_ids)
        if key not in state_cache:
            state_cache[key] = evaluate_protocol_state(
                item_ids,
                estimates_by_id,
                specs,
                context,
            )
        return state_cache[key]

    current_ids = initial_ids
    current_state = evaluate_ids(current_ids)
    initial_state = current_state
    current_objective_value = state_objective_value(current_state, objective, wtp)
    path: list[dict[str, Any]] = []

    for step in range(1, max_steps + 1):
        best_ids: list[str] | None = None
        best_state: dict[str, Any] | None = None
        best_objective_value = current_objective_value
        for neighbor_ids in protocol_optimizer_neighbors(
            current_ids,
            universe_ids,
            exclusive_groups,
        ):
            neighbor_state = evaluate_ids(neighbor_ids)
            neighbor_objective_value = state_objective_value(
                neighbor_state,
                objective,
                wtp,
            )
            if neighbor_objective_value > best_objective_value + min_improvement:
                best_ids = neighbor_ids
                best_state = neighbor_state
                best_objective_value = neighbor_objective_value

        if best_ids is None or best_state is None:
            break

        path.append(
            build_optimizer_step(
                step=step,
                previous_ids=current_ids,
                new_ids=best_ids,
                previous_state=current_state,
                new_state=best_state,
                previous_objective_value=current_objective_value,
                new_objective_value=best_objective_value,
                objective=objective,
                wtp=wtp,
                estimates_by_id=estimates_by_id,
            )
        )
        current_ids = best_ids
        current_state = best_state
        current_objective_value = best_objective_value

    delta_draws = current_state["_draws"] - initial_state["_draws"]
    delta_qaly = float(np.mean(delta_draws))
    delta_cost = protocol_state_cost(current_state) - protocol_state_cost(initial_state)
    transition = state_transition_actions(initial_ids, current_ids)
    return {
        "objective": objective,
        "wtp": wtp,
        "search_strategy": "greedy_full_state_local_search",
        "max_steps": max_steps,
        "steps_taken": len(path),
        "initial_state": public_state_payload(initial_state),
        "recommended_state": public_state_payload(current_state),
        "delta_qaly": round(delta_qaly, 4),
        "delta_days": round(delta_qaly * 365.25, 1),
        "p_positive_delta": round(float(np.mean(delta_draws > 0)), 4),
        "delta_cost": round(delta_cost, 2),
        "cost_per_qaly": marginal_cost_per_qaly(delta_cost, delta_qaly),
        "delta_net_benefit": round(
            state_objective_value(current_state, "net_benefit", wtp)
            - state_objective_value(initial_state, "net_benefit", wtp),
            2,
        ),
        "delta_ci80": [
            round(float(np.percentile(delta_draws, 10)), 4),
            round(float(np.percentile(delta_draws, 90)), 4),
        ],
        "actions_from_current": transition,
        "add_names": [estimates_by_id[item_id]["name"] for item_id in transition["add"]],
        "drop_names": [estimates_by_id[item_id]["name"] for item_id in transition["drop"]],
        "path": path,
        "exclusive_groups": exclusive_groups,
        "evaluated_state_count": len(state_cache),
    }


def build_protocol_optimizers(
    protocol_items: list[dict[str, Any]],
    estimates_by_id: dict[str, dict[str, Any]],
    specs: dict[str, StackSpec],
    context: ProtocolContext,
    *,
    wtp: float = PROTOCOL_OPTIMIZER_WTP,
) -> dict[str, Any]:
    return {
        "net_benefit": optimize_protocol_state(
            protocol_items,
            estimates_by_id,
            specs,
            context,
            objective="net_benefit",
            wtp=wtp,
        ),
        "qaly": optimize_protocol_state(
            protocol_items,
            estimates_by_id,
            specs,
            context,
            objective="qaly",
            wtp=wtp,
        ),
    }


def public_state_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if not key.startswith("_")}


def render_state_marginal_decision_table(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return ["_None._"]
    lines = [
        "| Action | Item | ΔQALY | Δdays | P(+Δ) | Δcost | $/QALY | Stack Δ |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['action']} | {row['name']} | {row['delta_qaly']:+.4f} | "
            f"{row['delta_days']:+.1f} | {row['p_positive']:.1%} | "
            f"${row['delta_cost']:,.0f} | {format_marginal_cost_per_qaly(row)} | "
            f"{row['state_interaction_delta_qaly']:+.4f} |"
        )
    return lines


def render_protocol_optimizer_table(optimizers: dict[str, Any]) -> list[str]:
    if not optimizers:
        return ["_None._"]
    lines = [
        "| Objective | ΔQALY | Δdays | P(+Δ) | Δcost | Net benefit | Adds | Drops | Steps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: |",
    ]
    for key in ("net_benefit", "qaly"):
        result = optimizers.get(key)
        if not result:
            continue
        adds = ", ".join(result["add_names"]) or "—"
        drops = ", ".join(result["drop_names"]) or "—"
        lines.append(
            f"| {key.replace('_', ' ')} | {result['delta_qaly']:+.4f} | "
            f"{result['delta_days']:+.1f} | {result['p_positive_delta']:.1%} | "
            f"${result['delta_cost']:,.0f} | ${result['delta_net_benefit']:,.0f} | "
            f"{adds} | {drops} | {result['steps_taken']} |"
        )
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Protocol Ground-Up Estimates")
    lines.append("")
    lines.append(
        "Fresh, personalized ground-up estimates using the live protocol inventory from `protocol-data.json` "
        "and personalization from `health.db`, rather than the existing protocol-page QALY outputs."
    )
    lines.append("")
    lines.append("## Reference Case")
    lines.append("")
    reference_case = payload["reference_case"]["base"]
    current_model = payload["reference_case"]["current_protocol_model"]
    lines.append(f"- Base reference case: {reference_case['name']}")
    lines.append(f"- Perspective: {reference_case['perspective']}")
    lines.append(
        f"- Reference-case discounting: {reference_case['health_discount_rate']:.1%} health, "
        f"{reference_case['cost_discount_rate']:.1%} costs"
    )
    lines.append(
        f"- Current protocol discounting: {current_model['health_discount_rate']:.1%} health"
        f", {current_model['cost_discount_rate']:.1%} costs"
    )
    lines.append(
        f"- Reference-case alignment: {current_model['reference_case_alignment']}; "
        f"formal reference case: {'yes' if current_model['is_formal_reference_case'] else 'no'}"
    )
    lines.append(f"- Utility gap: {current_model['gap']}")
    lines.append("")
    lines.append("## Baseline")
    lines.append("")
    lines.append(
        f"- Generated: {payload['generated_at']}"
    )
    lines.append(
        f"- 90-day combined sleep: {payload['baseline']['derived']['combined_sleep_h_90d']} h/night "
        f"(Whoop {payload['baseline']['sleep_90d']['whoop_sleep_h']} h, Eight Sleep {payload['baseline']['sleep_90d']['eight_sleep_h']} h)"
    )
    lines.append(
        f"- 90-day Whoop recovery: {payload['baseline']['sleep_90d']['whoop_recovery']}; "
        f"Eight Sleep score: {payload['baseline']['sleep_90d']['eight_score']}"
    )
    lines.append(
        f"- Modeled annual sleep-burden drag: {payload['baseline']['derived']['sleep_burden_annual_qaly']:.4f} QALY/year "
        f"from direct sleep-related utility loss"
    )
    lines.append(
        "- Sleep burden components: "
        + ", ".join(
            f"{name} {value:.4f}"
            for name, value in payload["baseline"]["derived"]["sleep_component_losses"].items()
            if value > 0
        )
    )
    lines.append(
        f"- Latest labs ({payload['baseline']['latest_lab_date']}): LDL {payload['baseline']['labs']['LDL']}, "
        f"HDL {payload['baseline']['labs']['HDL']}, TG {payload['baseline']['labs']['Triglycerides']}, "
        f"HbA1c {payload['baseline']['labs']['HbA1c']}, Vitamin D {payload['baseline']['labs']['Vitamin D']}, "
        f"eGFR {payload['baseline']['labs']['eGFR']}, creatinine {payload['baseline']['labs']['Creatinine']}"
    )
    lines.append("")
    lines.append(
        f"- Reference-case audit: {payload['summary']['items_needing_utility_lineage']} "
        "items still need explicit preference-based utility lineage; "
        f"{payload['summary']['items_using_fallback_utility_lineage']} items use fallback disability-weight lineage"
    )
    lines.append("")
    lines.append("## Current State")
    lines.append("")
    current_state = payload["current_state"]
    lines.append(
        f"- Full-state value: {current_state['total_qaly']:.4f} QALY "
        f"({current_state['total_days']:.1f} days)"
    )
    lines.append(
        f"- Additive standalone value: {current_state['additive_qaly']:.4f} QALY; "
        f"shared stack adjustment: {current_state['stack_interaction_qaly']:.4f} QALY"
    )
    if current_state["interaction_details"]:
        lines.append(
            "- Shared interaction adjustments: "
            + ", ".join(
                f"{detail['id']} {detail['penalty_qaly']:.4f}"
                for detail in current_state["interaction_details"]
            )
        )
    lines.append("")
    lines.append("## Marginal Decisions")
    lines.append("")
    lines.append(
        "Decision rows are computed as V(new full state) - V(current full state), "
        "so shared stack effects are counted once."
    )
    lines.append("")
    lines.extend(render_state_marginal_decision_table(payload["state_marginal_decisions"][:30]))
    lines.append("")
    lines.append("## Constrained Optimizer")
    lines.append("")
    lines.append(
        "The optimizer searches full protocol states with exclusive groups enforced "
        "(for example, one cardio mode and one primary OSA therapy), rather than "
        "treating every positive marginal as independently addable."
    )
    lines.append("")
    lines.extend(render_protocol_optimizer_table(payload["protocol_optimizers"]))
    lines.append("")
    lines.append("## Current Stack Drop Table")
    lines.append("")
    lines.append(
        "Positive Drop ΔQALY means stopping the item is expected to help; negative means stopping is expected to hurt. "
        "These are full-state marginal drop values."
    )
    lines.append("")
    lines.extend(render_current_stack_drop_table(payload["current_stack_drop_table"]))
    lines.append("")
    lines.append("## Decision Slices")
    lines.append("")
    lines.append("### Actionable By Total QALY")
    lines.append("")
    lines.extend(render_ranking_table(payload["rankings"]["actionable_by_total_qaly"]))
    lines.append("")
    lines.append("### Actionable By $/QALY")
    lines.append("")
    lines.extend(render_ranking_table(payload["rankings"]["actionable_by_cost_per_qaly"]))
    lines.append("")
    lines.append("### Supplement Candidates By $/QALY")
    lines.append("")
    lines.extend(
        render_ranking_table(
            payload["rankings"]["supplement_candidates_by_cost_per_qaly"]
        )
    )
    lines.append("")
    lines.append("### Free Positive Actions")
    lines.append("")
    lines.extend(render_ranking_table(payload["rankings"]["free_positive_actions"]))
    lines.append("")
    lines.append("### Negative Actionable Items")
    lines.append("")
    lines.extend(render_ranking_table(payload["rankings"]["negative_actionable"]))
    lines.append("")
    lines.append("## Ranking")
    lines.append("")
    lines.append(
        "| Item | Status | Type | Total QALY | Days | Cost | $/QALY | "
        "Mortality QALY | Direct Harm | QOL QALY |"
    )
    lines.append(
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    for item in payload["items"]:
        cpq = "—" if item["cost_per_qaly"] is None else f"${item['cost_per_qaly']:,}"
        lines.append(
            f"| {item['name']} | {item['status']} | {item['display_category']} | "
            f"{item['total_qaly']:.4f} | {item['days']:.1f} | "
            f"${item['modeled_total_cost']:,.0f} | {cpq} | "
            f"{item['mortality_qaly']:.4f} | {item['direct_harm_qaly']:.4f} | {item['qol_qaly']:.4f} |"
        )
    lines.append("")
    lines.append("## Notes By Item")
    lines.append("")
    for item in payload["items"]:
        lines.append(f"### {item['name']}")
        lines.append("")
        lines.append(
            f"- Estimate: {item['total_qaly']:.4f} QALY ({item['days']:.1f} days), "
            f"sanity range [{item['range_low_qaly']:.3f}, {item['range_high_qaly']:.3f}]"
        )
        lines.append(f"- Reference-case status: {item['reference_case_status']}")
        if item["qaly_lineage"]["issues"]:
            lines.append(
                "- Utility-lineage gaps: "
                + ", ".join(item["qaly_lineage"]["issues"])
            )
        lines.append(f"- Why: {item['rationale']}")
        lines.append(f"- Personalization: {item['personalization']}")
        if item["sources"]:
            lines.append(f"- Sources: {', '.join(item['sources'])}")
        else:
            lines.append("- Sources: no robust, directly on-point human outcome source found in this pass")
        lines.append("")
    return "\n".join(lines)


def main(context: ProtocolContext | None = None) -> None:
    context = resolve_protocol_context(context)
    baseline = load_baseline(context)
    specs = build_specs(baseline, context)
    specs.update(build_additional_specs(baseline, context))
    protocol_items = load_protocol_items(context)

    missing = [item["id"] for item in protocol_items if item["id"] not in specs]
    if missing:
        raise RuntimeError(f"Missing specs for protocol items: {missing}")

    internal_estimates = [
        estimate_item(
            item,
            specs[item["id"]],
            baseline,
            context,
            active_interaction_tags=(),
            include_draws=True,
        )
        for item in protocol_items
    ]
    estimates_by_id = {item["id"]: item for item in internal_estimates}
    current_state = evaluate_protocol_state(
        active_state_item_ids(protocol_items),
        estimates_by_id,
        specs,
        context,
    )
    state_marginal_decisions = build_state_marginal_decision_table(
        protocol_items,
        estimates_by_id,
        specs,
        context,
    )
    protocol_optimizers = build_protocol_optimizers(
        protocol_items,
        estimates_by_id,
        specs,
        context,
    )
    estimates = [public_estimate_payload(item) for item in internal_estimates]
    estimates.sort(key=lambda x: x["total_qaly"], reverse=True)
    current_stack_drop_table = [
        row for row in state_marginal_decisions if row["action"] == "drop"
    ]

    payload = {
        "generated_at": date.today().isoformat(),
        "profile": profile_payload(context.profile),
        "reference_case": reference_case_payload(),
        "assumptions": {
            "qaly_discount_rate": QALY_DISCOUNT_RATE,
            "cost_discount_rate": COST_DISCOUNT_RATE,
            "n_simulations": N_SIMULATIONS,
            "method": (
                "Fresh item-by-item assumptions: structured components are simulated through "
                "Optiqal's vectorized lifecycle model with skeptical confounding priors and direct harms; "
                "quality-of-life components are hand-estimated annual utilities discounted "
                "over item-specific durability windows."
            ),
            "state_draw_model": {
                "type": "paired_latent_rank_copula",
                "description": (
                    "Each Monte Carlo row is treated as one latent personal world. Item draws keep "
                    "their original marginal distributions but are rank-paired through shared global, "
                    "mechanism, and category factors before full-state values and marginal deltas are "
                    "computed."
                ),
                "global_score_weight": LATENT_GLOBAL_SCORE_WEIGHT,
                "mechanism_score_weight": LATENT_MECHANISM_SCORE_WEIGHT,
                "category_score_weight": LATENT_CATEGORY_SCORE_WEIGHT,
                "max_shared_score_weight": LATENT_MAX_SHARED_SCORE_WEIGHT,
            },
            "protocol_optimizer": {
                "wtp": PROTOCOL_OPTIMIZER_WTP,
                "max_steps": PROTOCOL_OPTIMIZER_MAX_STEPS,
                "min_improvement": PROTOCOL_OPTIMIZER_MIN_IMPROVEMENT,
                "search_strategy": "greedy_full_state_local_search",
            },
            "caveat": (
                "These are explicit judgment calls, not clinical truth. The point is to create "
                "a transparent, reusable benchmark that can later be upgraded to a study-level Bayesian model."
            ),
        },
        "baseline": baseline,
        "summary": {
            "n_items": len(estimates),
            "total_stack_qaly": current_state["total_qaly"],
            "total_stack_days": current_state["total_days"],
            "standalone_additive_qaly": current_state["additive_qaly"],
            "state_stack_interaction_qaly": current_state["stack_interaction_qaly"],
            "items_within_range": sum(1 for item in estimates if item["within_range"]),
            "items_outside_range": sum(1 for item in estimates if not item["within_range"]),
            "items_needing_utility_lineage": sum(
                1
                for item in estimates
                if item["reference_case_status"] == "needs_utility_lineage"
            ),
            "items_using_fallback_utility_lineage": sum(
                1
                for item in estimates
                if any(
                    "uses_fallback" in issue
                    for issue in item["qaly_lineage"]["issues"]
                )
            ),
        },
        "current_state": public_state_payload(current_state),
        "state_marginal_decisions": state_marginal_decisions,
        "protocol_optimizers": protocol_optimizers,
        "current_stack_drop_table": current_stack_drop_table,
        "rankings": build_decision_rankings(estimates),
        "items": estimates,
    }

    context.output_json.write_text(json.dumps(payload, indent=2) + "\n")
    context.output_md.write_text(render_markdown(payload) + "\n")

    top = estimates[:8]
    print("Wrote:")
    print(f"  {context.output_json}")
    print(f"  {context.output_md}")
    print("")
    print("Top items by personalized ground-up total QALY:")
    for item in top:
        print(f"  {item['name']:<28} {item['total_qaly']:>7.4f} QALY  ({item['days']:>5.1f} days)")
    print("")
    print(f"Total stack: {payload['summary']['total_stack_qaly']:.4f} QALY ({payload['summary']['total_stack_days']:.1f} days)")
    print(
        f"Sanity check: {payload['summary']['items_within_range']}/{payload['summary']['n_items']} "
        "item estimates inside predeclared ranges"
    )
    outside = [item for item in estimates if not item["within_range"]]
    if outside:
        print("Outside range:")
        for item in outside:
            print(
                f"  {item['name']}: {item['total_qaly']:.4f} vs "
                f"[{item['range_low_qaly']:.4f}, {item['range_high_qaly']:.4f}]"
            )


if __name__ == "__main__":
    main()
