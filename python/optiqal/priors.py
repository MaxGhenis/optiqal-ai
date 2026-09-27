"""Strict loader for the hand-set priors used by the Optiqal engine."""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PRIORS_PATH = Path(__file__).with_name("data") / "priors.yaml"

_CATEGORY_KEYS = {
    "exercise",
    "diet",
    "sleep",
    "stress",
    "substance",
    "medical",
    "social",
    "other",
}
_AUTHORED_INTERVENTION_KEYS = {
    "daily_exercise_moderate",
    "daily_sunscreen",
    "fish_oil_supplement",
    "meditation_daily",
    "mediterranean_diet",
    "moderate_alcohol",
    "quit_smoking",
    "sleep_8_hours",
    "strength_training",
    "walking_30min_daily",
}
_INTERVENTION_KEYS = {
    "17a_estradiol",
    "acarbose_50mg",
    "alpha_lipoic_acid_300",
    "apap_nightly",
    "apigenin_50",
    "ashwagandha_600",
    "aspirin_81mg",
    "astaxanthin_12",
    "berberine_500",
    "black_seed_oil_1g",
    "boron_3",
    "bpc157_cycle",
    "broccoli_seed_200",
    "caakg_2000",
    "cistanche_200",
    "cocoa_flavanols_500",
    "collagen_22g",
    "creatine_5g",
    "curcumin_250",
    "daily_exercise_moderate",
    "daily_sunscreen",
    "daridorexant_25mg",
    "doxepin_3mg",
    "egcg_400",
    "empagliflozin",
    "ergothioneine_5",
    "finasteride_1.25mg",
    "fisetin_100",
    "fisetin_100_unbundled",
    "fish_oil_supplement",
    "garlic_1200",
    "ghk_cu",
    "ginger_400",
    "glucosamine_sulfate_750",
    "glutathione_250",
    "glycine_2g",
    "hbot_60sessions",
    "head_elevation_nightly",
    "hiit_1x_week",
    "hiit_2x_week",
    "hiit_3x_week",
    "humidifier_nightly",
    "hyaluronic_acid_120",
    "infrared_sauna_4x_week",
    "l_lysine_1000",
    "l_theanine_200",
    "l_theanine_200_bedtime",
    "eight_sleep_pod6_upgrade",
    "lemborexant_5mg",
    "lions_mane_1g",
    "lithium_1mg_orotate",
    "lithium_5mg",
    "lutein_zeaxanthin",
    "luteolin_100",
    "luteolin_100_unbundled",
    "lycopene_15",
    "magnesium_200",
    "magnesium_citrate_150",
    "meditation_daily",
    "mediterranean_diet",
    "melatonin_300mcg",
    "metformin_500mg",
    "moderate_alcohol",
    "mouth_tape_nightly",
    "nac_1200",
    "nasacort_nightly",
    "nasal_strips_nightly",
    "nmn_500",
    "nr_300",
    "nr_300_unbundled",
    "omega3_clo",
    "omega3_epa_2g",
    "oral_appliance_custom",
    "pqq_20",
    "prebiotics",
    "probiotic_daily",
    "pterostilbene_50",
    "quercetin_500",
    "quit_smoking",
    "rapamycin_5mg_wk",
    "semaglutide",
    "sleep_8_hours",
    "spermidine_10",
    "statin_5mg",
    "strength_maintenance",
    "strength_training",
    "sulforaphane_20_extra",
    "suvorexant_10mg",
    "tadalafil_2.5mg",
    "taurine_500_topup",
    "tb500_cycle",
    "tempo_run_1x_week",
    "tmg_1g",
    "traditional_sauna_4x_week",
    "trazodone_50mg",
    "ubiquinol_50",
    "ubiquinol_50_unbundled",
    "urolithin_a_500",
    "vitamin_c_500_extra",
    "vitamin_d_2000",
    "vitamin_k2",
    "walking_30min_daily",
    "zinc_carnosine_75",
    "zone2_cardio_2x_week",
}
_PROTOCOL_INTERVENTION_KEYS = {
    "17a_estradiol",
    "acarbose_50mg",
    "alpha_lipoic_acid_300",
    "apigenin_50",
    "ashwagandha_600",
    "aspirin_81mg",
    "astaxanthin_12",
    "berberine_500",
    "black_seed_oil_1g",
    "boron_3",
    "bpc157_cycle",
    "broccoli_seed_200",
    "cistanche_200",
    "cocoa_flavanols_500",
    "collagen_22g",
    "creatine_5g",
    "curcumin_250",
    "egcg_400",
    "empagliflozin",
    "ergothioneine_5",
    "finasteride_1.25mg",
    "fisetin_100",
    "fisetin_100_unbundled",
    "garlic_1200",
    "ghk_cu",
    "ginger_400",
    "glycine_2g",
    "hbot_60sessions",
    "head_elevation_nightly",
    "hiit_1x_week",
    "hiit_2x_week",
    "hiit_3x_week",
    "hyaluronic_acid_120",
    "infrared_sauna_4x_week",
    "lions_mane_1g",
    "lithium_1mg_orotate",
    "lithium_5mg",
    "lutein_zeaxanthin",
    "luteolin_100",
    "luteolin_100_unbundled",
    "lycopene_15",
    "magnesium_200",
    "melatonin_300mcg",
    "metformin_500mg",
    "nac_1200",
    "nmn_500",
    "nr_300",
    "nr_300_unbundled",
    "omega3_clo",
    "omega3_epa_2g",
    "pqq_20",
    "prebiotics",
    "probiotic_daily",
    "pterostilbene_50",
    "quercetin_500",
    "rapamycin_5mg_wk",
    "semaglutide:not_weight_indicated",
    "semaglutide:weight_indicated",
    "spermidine_10",
    "statin_5mg",
    "strength_maintenance",
    "sulforaphane_20_extra",
    "tadalafil_2.5mg",
    "taurine_500_topup",
    "tb500_cycle",
    "tempo_run_1x_week",
    "tmg_1g",
    "traditional_sauna_4x_week",
    "trazodone_50mg",
    "ubiquinol_50",
    "ubiquinol_50_unbundled",
    "urolithin_a_500",
    "vitamin_c_500_extra",
    "vitamin_d_2000",
    "vitamin_k2",
    "zinc_carnosine_75",
    "zone2_cardio_2x_week",
}
_EVIDENCE_ADJUSTMENT_KEYS = {
    "meta-analysis",
    "rct",
    "cohort",
    "case-control",
    "review",
    "other",
}
_MORTALITY_STUDY_QUALITY_KEYS = {
    "rct_preregistered_hard_endpoint",
    "rct_standard",
    "mendelian_randomization",
    "meta_analysis_rcts",
    "cohort_meta_analysis",
    "cohort_large",
    "cohort_small",
    "case_control",
    "supplement_industry_rct",
    "observational_speculative",
    "animal_or_mechanistic",
}
_QOL_STUDY_QUALITY_KEYS = {
    "rct_objective_endpoint",
    "meta_analysis_placebo_rcts",
    "rct_placebo_patient_reported",
    "rct_open_label",
    "supplement_industry_rct",
    "observational_symptom",
    "mechanistic_or_self_experiment",
}
_QOL_CATEGORY_KEYS = {
    "sleep_symptom",
    "respiratory_airway",
    "sexual_function",
    "mood_stress",
    "pain_joint",
    "gi_symptom",
    "cognitive",
    "hair_skin",
    "fitness_function",
    "metabolic_symptom",
    "general_vitality",
}
_EVIDENCE_EFFECT_KEYS = {"high", "moderate", "low", "very-low"}


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path} keys must be strings")
    return value


def _exact_keys(value: dict[str, Any], expected: set[str], path: str) -> None:
    missing = expected - value.keys()
    unknown = value.keys() - expected
    if missing:
        raise ValueError(f"{path} is missing keys: {sorted(missing)}")
    if unknown:
        raise ValueError(f"{path} has unknown keys: {sorted(unknown)}")


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{path} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{path} must be finite")
    return numeric


def _source(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")


def _beta_row(value: Any, path: str, *, metadata: bool) -> None:
    row = _mapping(value, path)
    expected = {"alpha", "beta", "source"}
    if metadata:
        expected |= {"rationale", "calibration_sources"}
    _exact_keys(row, expected, path)
    for parameter in ("alpha", "beta"):
        if _number(row[parameter], f"{path}.{parameter}") <= 0:
            raise ValueError(f"{path}.{parameter} must be positive")
    _source(row["source"], f"{path}.source")
    if metadata:
        if not isinstance(row["rationale"], str):
            raise ValueError(f"{path}.rationale must be a string")
        calibration_sources = row["calibration_sources"]
        if not isinstance(calibration_sources, list) or not all(
            isinstance(item, str) for item in calibration_sources
        ):
            raise ValueError(f"{path}.calibration_sources must be a list of strings")


def _fixed_table(
    value: Any,
    path: str,
    expected: set[str],
    validate_row: Any,
) -> dict[str, Any]:
    table = _mapping(value, path)
    _exact_keys(table, expected, path)
    for key, row in table.items():
        validate_row(row, f"{path}.{key}")
    return table


def _retention_row(value: Any, path: str) -> None:
    row = _mapping(value, path)
    _exact_keys(row, {"retention", "source"}, path)
    retention = _number(row["retention"], f"{path}.retention")
    if not 0 <= retention <= 1:
        raise ValueError(f"{path}.retention must be in [0, 1]")
    _source(row["source"], f"{path}.source")


def _multiplier_row(value: Any, path: str, field: str) -> None:
    row = _mapping(value, path)
    _exact_keys(row, {field, "source"}, path)
    if _number(row[field], f"{path}.{field}") <= 0:
        raise ValueError(f"{path}.{field} must be positive")
    _source(row["source"], f"{path}.source")


def _validate_priors(data: Any) -> dict[str, Any]:
    root = _mapping(data, "priors")
    _exact_keys(
        root,
        {
            "version",
            "confounding",
            "evidence_adjustments",
            "study_quality_shrinkage",
            "qol_transport",
            "evidence_effect_multipliers",
        },
        "priors",
    )
    if root["version"] != 1 or isinstance(root["version"], bool):
        raise ValueError("priors.version must be 1")

    confounding = _mapping(root["confounding"], "priors.confounding")
    _exact_keys(
        confounding,
        {"categories", "interventions", "protocol_interventions"},
        "priors.confounding",
    )
    _fixed_table(
        confounding["categories"],
        "priors.confounding.categories",
        _CATEGORY_KEYS,
        lambda row, path: _beta_row(row, path, metadata=True),
    )
    interventions = _mapping(
        confounding["interventions"], "priors.confounding.interventions"
    )
    _exact_keys(
        interventions,
        _INTERVENTION_KEYS,
        "priors.confounding.interventions",
    )
    for key, row in interventions.items():
        _beta_row(
            row,
            f"priors.confounding.interventions.{key}",
            metadata=key in _AUTHORED_INTERVENTION_KEYS,
        )
    protocol_interventions = _mapping(
        confounding["protocol_interventions"],
        "priors.confounding.protocol_interventions",
    )
    _exact_keys(
        protocol_interventions,
        _PROTOCOL_INTERVENTION_KEYS,
        "priors.confounding.protocol_interventions",
    )
    for key, row in protocol_interventions.items():
        _beta_row(
            row,
            f"priors.confounding.protocol_interventions.{key}",
            metadata=False,
        )

    _fixed_table(
        root["evidence_adjustments"],
        "priors.evidence_adjustments",
        _EVIDENCE_ADJUSTMENT_KEYS,
        lambda row, path: _multiplier_row(row, path, "alpha_multiplier"),
    )
    _fixed_table(
        root["study_quality_shrinkage"],
        "priors.study_quality_shrinkage",
        _MORTALITY_STUDY_QUALITY_KEYS,
        _retention_row,
    )

    qol_transport = _mapping(root["qol_transport"], "priors.qol_transport")
    _exact_keys(
        qol_transport,
        {"study_quality_shrinkage", "categories", "authored_residual_optimism"},
        "priors.qol_transport",
    )
    _fixed_table(
        qol_transport["study_quality_shrinkage"],
        "priors.qol_transport.study_quality_shrinkage",
        _QOL_STUDY_QUALITY_KEYS,
        _retention_row,
    )
    _fixed_table(
        qol_transport["categories"],
        "priors.qol_transport.categories",
        _QOL_CATEGORY_KEYS,
        lambda row, path: _beta_row(row, path, metadata=True),
    )
    _beta_row(
        qol_transport["authored_residual_optimism"],
        "priors.qol_transport.authored_residual_optimism",
        metadata=True,
    )

    _fixed_table(
        root["evidence_effect_multipliers"],
        "priors.evidence_effect_multipliers",
        _EVIDENCE_EFFECT_KEYS,
        lambda row, path: _multiplier_row(row, path, "multiplier"),
    )
    return root


@lru_cache(maxsize=None)
def load_priors(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the prior registry, caching each resolved path."""
    resolved = PRIORS_PATH if path is None else Path(path)
    try:
        with resolved.open(encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid priors YAML at {resolved}: {error}") from error
    return _validate_priors(data)
