"""Shared payload handlers for Optiqal web-facing baseline and frontier APIs."""

from __future__ import annotations

import math
from typing import Any, Dict, Literal, Optional

from optiqal import (
    AnalysisConfig,
    PublicPolicy,
    Profile,
    analyze,
    build_public_policy_spec,
    build_public_sleep_decision_sequence,
    build_public_sleep_decision_specs,
    build_stack_interaction_penalty_fn,
    evaluate_decision_states,
    get_catalog,
    has_meaningful_public_airway_signal,
    has_meaningful_public_nasal_dryness_signal,
    has_meaningful_public_osa_therapy_signal,
    is_publicly_rankable,
    public_display_category,
    public_display_name,
    public_recommendation_lane,
    public_rankability_reason,
    rank_interventions_by_marginal_cost_per_qaly,
    serialize_decision_sequence,
    serialize_decision_state_evaluations,
)
from optiqal.lifecycle import CONDITION_DECREMENTS, get_mortality_rate, get_quality_weight
from optiqal.defaults import DEFAULT_QALY_DISCOUNT_RATE
from optiqal.profile import (
    ACTIVITY_MORTALITY_RR,
    BMI_MORTALITY_RR,
    DIABETES_MORTALITY_RR,
    HYPERTENSION_MORTALITY_RR,
    SMOKING_MORTALITY_RR,
)
from optiqal.sleep import SleepMetrics, estimate_sleep_burden, sleep_baseline_mortality_multiplier


Sex = Literal["male", "female"]

CALIBRATION_BY_AGE_SEX: dict[str, dict[str, float]] = {
    "18-24": {"male": 1.8136, "female": 1.8746},
    "25-34": {"male": 2.4368, "female": 2.4272},
    "35-44": {"male": 2.6050, "female": 2.5871},
    "45-54": {"male": 2.7883, "female": 3.0324},
    "55-64": {"male": 3.0901, "female": 2.9073},
    "65-74": {"male": 2.9299, "female": 3.0071},
    "75-84": {"male": 2.8262, "female": 2.9369},
}
CALIBRATION_BY_SEX = {"male": 2.6415, "female": 2.6912}
AGE_GROUP_BOUNDS = [
    (18, 24, "18-24"),
    (25, 34, "25-34"),
    (35, 44, "35-44"),
    (45, 54, "45-54"),
    (55, 64, "55-64"),
    (65, 74, "65-74"),
    (75, 84, "75-84"),
]
MAX_AGE = 110
ACCESS_COVERAGE_RANK = {"likely": 0, "na": 0, "mixed": 1, "unlikely": 2}
ACCESS_FRICTION_RANK = {"low": 0, "medium": 1, "high": 2}


def _clean_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _bmi_category(weight_kg: float, height_cm: float) -> str:
    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    if bmi < 25:
        return "normal"
    if bmi < 30:
        return "overweight"
    if bmi < 35:
        return "obese"
    return "severely_obese"


def _sexes(value: str) -> list[Sex]:
    if value == "other":
        return ["male", "female"]
    return [value if value in {"male", "female"} else "male"]  # type: ignore[list-item]


def _build_sleep_metrics(
    payload: Dict[str, Any], fallback_duration: Optional[float] = None
) -> Optional[SleepMetrics]:
    fields = {
        "duration_hours": _clean_float(payload.get("duration_hours")) or fallback_duration,
        "recovery_score": _clean_float(payload.get("recovery_score")),
        "sleep_quality_score": _clean_float(payload.get("sleep_quality_score")),
        "waso_min": _clean_float(payload.get("waso_min")),
        "routine_score": _clean_float(payload.get("routine_score")),
        "social_jetlag_min": _clean_float(payload.get("social_jetlag_min")),
        "latency_min": _clean_float(payload.get("latency_min")),
        "breathing_score": _clean_float(payload.get("breathing_score")),
        "spo2": _clean_float(payload.get("spo2")),
        "snore_pct": _clean_float(payload.get("snore_pct")),
        "sleep_debt_min": _clean_float(payload.get("sleep_debt_min")),
        "airway_response_signal": _clean_float(payload.get("airway_response_signal")),
    }
    if not any(value is not None for value in fields.values()):
        return None
    return SleepMetrics(**fields)


def _get_calibration_factor(age: int, sex: Sex) -> float:
    for min_age, max_age, label in AGE_GROUP_BOUNDS:
        if min_age <= age <= max_age:
            return CALIBRATION_BY_AGE_SEX[label][sex]
    return CALIBRATION_BY_SEX[sex]


def _condition_quality_decrement(has_diabetes: bool, has_hypertension: bool) -> float:
    decrement = 0.0
    if has_diabetes:
        decrement += float(CONDITION_DECREMENTS["diabetes"])
    if has_hypertension:
        decrement += float(CONDITION_DECREMENTS["hypertension"])
    return decrement


def _calculate_projection(
    *,
    age: int,
    sex: Sex,
    mortality_multiplier: float,
    quality_decrement: float,
    discount_rate: float,
) -> dict[str, Any]:
    survival = 1.0
    remaining_life_expectancy = 0.0
    remaining_qalys = 0.0
    # Discounted QALYs accrued while alive (NOT survival-weighted): the lifetime
    # QALYs realized by someone who dies in a given year. Used for the interval.
    realized_qalys = 0.0
    current_quality_weight = max(0.0, get_quality_weight(age) - quality_decrement)
    curve: list[dict[str, float]] = []

    # Age-at-death prediction interval, captured as cumulative survival decays.
    # When survival first falls to <= t, ~(1 - t) of the cohort has died by this
    # age, so that year is the (1 - t) percentile of age at death.
    death_targets = {"p10": 0.90, "p50": 0.50, "p90": 0.10}
    le_at: dict[str, float] = {}
    qalys_at: dict[str, float] = {}
    last_year = 0

    for year in range(max(0, MAX_AGE - age + 1)):
        current_age = age + year
        base_qx = min(get_mortality_rate(current_age, sex) * mortality_multiplier, 0.99)
        quality_weight = max(0.0, get_quality_weight(current_age) - quality_decrement)
        discount = 1.0 / ((1.0 + discount_rate) ** year)
        expected_qaly = survival * quality_weight * discount

        remaining_life_expectancy += survival
        remaining_qalys += expected_qaly
        realized_qalys += quality_weight * discount

        for key, threshold in death_targets.items():
            if key not in le_at and survival <= threshold:
                le_at[key] = float(year)
                qalys_at[key] = float(realized_qalys)

        if year == 0 or current_age % 5 == 0 or survival < 0.02:
            curve.append(
                {
                    "age": float(current_age),
                    "survival_probability": float(survival),
                    "quality_weight": float(quality_weight),
                    "expected_qaly": float(expected_qaly),
                }
            )

        last_year = year
        survival *= 1.0 - base_qx
        if survival < 0.001:
            break

    # Percentiles not reached within the horizon clamp to the horizon end.
    for key in death_targets:
        le_at.setdefault(key, float(last_year))
        qalys_at.setdefault(key, float(realized_qalys))

    return {
        "remaining_life_expectancy": remaining_life_expectancy,
        "expected_death_age": age + remaining_life_expectancy,
        "remaining_qalys": remaining_qalys,
        "current_quality_weight": current_quality_weight,
        "curve": curve,
        "remaining_life_expectancy_ci": [le_at["p10"], le_at["p90"]],
        "expected_death_age_ci": [age + le_at["p10"], age + le_at["p90"]],
        "remaining_qalys_ci": [qalys_at["p10"], qalys_at["p90"]],
    }


def _average_curves(curves: list[list[dict[str, float]]]) -> list[dict[str, float]]:
    by_age: dict[int, dict[str, list[float]]] = {}
    for curve in curves:
        for point in curve:
            age = int(point["age"])
            bucket = by_age.setdefault(
                age,
                {
                    "survival_probability": [],
                    "quality_weight": [],
                    "expected_qaly": [],
                },
            )
            bucket["survival_probability"].append(point["survival_probability"])
            bucket["quality_weight"].append(point["quality_weight"])
            bucket["expected_qaly"].append(point["expected_qaly"])

    result: list[dict[str, float]] = []
    for age in sorted(by_age):
        bucket = by_age[age]
        result.append(
            {
                "age": float(age),
                "survival_probability": sum(bucket["survival_probability"]) / len(bucket["survival_probability"]),
                "quality_weight": sum(bucket["quality_weight"]) / len(bucket["quality_weight"]),
                "expected_qaly": sum(bucket["expected_qaly"]) / len(bucket["expected_qaly"]),
            }
        )
    return result


def build_baseline_response(payload: Dict[str, Any]) -> dict[str, Any]:
    profile_payload = payload.get("profile") or {}
    sleep_payload = payload.get("sleep_metrics") or {}

    age = int(profile_payload["age"])
    sex_value = str(profile_payload.get("sex", "male"))
    weight_kg = float(profile_payload["weight_kg"])
    height_cm = float(profile_payload["height_cm"])
    smoker = bool(profile_payload.get("smoker"))
    has_diabetes = bool(profile_payload.get("has_diabetes"))
    has_hypertension = bool(profile_payload.get("has_hypertension"))
    activity_level = str(profile_payload.get("activity_level", "light"))
    sleep_hours = _clean_float(profile_payload.get("sleep_hours_per_night"))

    bmi_category = _bmi_category(weight_kg, height_cm)
    sleep_metrics = _build_sleep_metrics(sleep_payload, sleep_hours)
    sleep_estimate = estimate_sleep_burden(sleep_metrics) if sleep_metrics is not None else None
    sleep_multiplier = sleep_baseline_mortality_multiplier(sleep_estimate)

    lifestyle_multiplier = (
        float(BMI_MORTALITY_RR[bmi_category])
        * float(SMOKING_MORTALITY_RR["current" if smoker else "never"])
        * float(ACTIVITY_MORTALITY_RR[activity_level])
    )
    condition_multiplier = (
        (float(DIABETES_MORTALITY_RR) if has_diabetes else 1.0)
        * (float(HYPERTENSION_MORTALITY_RR) if has_hypertension else 1.0)
    )
    raw_multiplier = lifestyle_multiplier * condition_multiplier * float(sleep_multiplier)

    projections = []
    curves = []
    calibration_factors = []
    calibrated_multipliers = []
    for sex in _sexes(sex_value):
        calibration_factor = _get_calibration_factor(age, sex)
        calibrated_multiplier = raw_multiplier / calibration_factor
        projection = _calculate_projection(
            age=age,
            sex=sex,
            mortality_multiplier=calibrated_multiplier,
            quality_decrement=_condition_quality_decrement(has_diabetes, has_hypertension),
            discount_rate=DEFAULT_QALY_DISCOUNT_RATE,
        )
        projections.append(projection)
        curves.append(projection["curve"])
        calibration_factors.append(calibration_factor)
        calibrated_multipliers.append(calibrated_multiplier)

    result = {
        "meta": {
            "model": "canonical_python_baseline",
            "qaly_discount_rate": DEFAULT_QALY_DISCOUNT_RATE,
            "explicit_inputs_only": True,
            "profile": {
                "age": age,
                "sex": sex_value,
                "bmi_category": bmi_category,
                "smoking_status": "current" if smoker else "never",
                "has_diabetes": has_diabetes,
                "has_hypertension": has_hypertension,
                "activity_level": activity_level,
            },
        },
        "point_estimate": {
            "remaining_life_expectancy": round(
                float(sum(p["remaining_life_expectancy"] for p in projections) / len(projections)),
                1,
            ),
            "expected_death_age": round(
                float(sum(p["expected_death_age"] for p in projections) / len(projections)),
                1,
            ),
            "remaining_qalys": round(
                float(sum(p["remaining_qalys"] for p in projections) / len(projections)),
                1,
            ),
            "current_quality_weight": round(
                float(sum(p["current_quality_weight"] for p in projections) / len(projections)),
                3,
            ),
            "remaining_life_expectancy_ci": [
                round(float(sum(p["remaining_life_expectancy_ci"][0] for p in projections) / len(projections)), 1),
                round(float(sum(p["remaining_life_expectancy_ci"][1] for p in projections) / len(projections)), 1),
            ],
            "expected_death_age_ci": [
                round(float(sum(p["expected_death_age_ci"][0] for p in projections) / len(projections)), 1),
                round(float(sum(p["expected_death_age_ci"][1] for p in projections) / len(projections)), 1),
            ],
            "remaining_qalys_ci": [
                round(float(sum(p["remaining_qalys_ci"][0] for p in projections) / len(projections)), 1),
                round(float(sum(p["remaining_qalys_ci"][1] for p in projections) / len(projections)), 1),
            ],
        },
        "risk": {
            "lifestyle_multiplier": round(float(lifestyle_multiplier), 4),
            "condition_multiplier": round(float(condition_multiplier), 4),
            "sleep_multiplier": round(float(sleep_multiplier), 4),
            "raw_multiplier": round(float(raw_multiplier), 4),
            "calibration_factor": round(float(sum(calibration_factors) / len(calibration_factors)), 4),
            "calibrated_multiplier": round(float(sum(calibrated_multipliers) / len(calibrated_multipliers)), 4),
        },
        "survival_curve": [
            {
                "age": int(point["age"]),
                "survival_probability": round(float(point["survival_probability"]), 4),
                "quality_weight": round(float(point["quality_weight"]), 4),
                "expected_qaly": round(float(point["expected_qaly"]), 4),
            }
            for point in _average_curves(curves)
        ],
        "sleep_estimate": None,
    }

    if sleep_estimate is not None:
        result["sleep_estimate"] = {
            "annual_qaly_loss": round(float(sleep_estimate.annual_qaly_loss), 4),
            "mortality_signal": round(float(sleep_estimate.mortality_signal), 4),
            "baseline_hazard_multiplier": round(float(sleep_multiplier), 6),
            "component_losses": {
                key: round(float(value), 4)
                for key, value in sleep_estimate.component_losses.items()
            },
        }

    return result


def _sort_items(item: Dict[str, Any]) -> tuple:
    positive = item["total_qaly"] > 0
    annual_cost = item["annual_cost"]
    cost_per_qaly = item["cost_per_qaly"]
    if annual_cost is None:
        sort_cost = float("inf")
    elif annual_cost <= 0:
        sort_cost = 0.0
    else:
        sort_cost = cost_per_qaly if cost_per_qaly is not None else float("inf")
    return (
        0 if positive else 1,
        sort_cost,
        -item["total_qaly"],
        item["name"].lower(),
    )


def _access_payload(entry) -> Dict[str, Any]:
    profile = entry.access_profile
    return {
        "tier": profile.tier,
        "coverage_outlook": profile.coverage_outlook,
        "friction": profile.friction,
        "notes": profile.notes,
    }


def _access_rank(access: Dict[str, Any]) -> tuple[int, int]:
    return (
        ACCESS_COVERAGE_RANK[access["coverage_outlook"]],
        ACCESS_FRICTION_RANK[access["friction"]],
    )


def _option_access_payload(item_ids: list[str], entries: Dict[str, Any]) -> Dict[str, Any]:
    if not item_ids:
        return {
            "tier": "none",
            "coverage_outlook": "na",
            "friction": "low",
            "notes": "No added intervention.",
            "item_accesses": [],
        }

    item_accesses = [_access_payload(entries[item_id]) for item_id in item_ids]
    worst_coverage = max(
        (access["coverage_outlook"] for access in item_accesses),
        key=lambda value: ACCESS_COVERAGE_RANK[value],
    )
    worst_friction = max(
        (access["friction"] for access in item_accesses),
        key=lambda value: ACCESS_FRICTION_RANK[value],
    )
    notes = [access["notes"] for access in item_accesses if access["notes"]]
    return {
        "tier": item_accesses[0]["tier"] if len(item_accesses) == 1 else "multiple",
        "coverage_outlook": worst_coverage,
        "friction": worst_friction,
        "notes": notes[0] if len(notes) == 1 else "Mixed access burden across added items.",
        "item_accesses": item_accesses,
    }


def _decision_spec_item_ids(spec: Any) -> list[str]:
    item_ids = list(getattr(spec, "base_item_ids", []))
    for option in getattr(spec, "options", []) or []:
        item_ids.extend(option.added_item_ids)
    return item_ids


def _decision_sequence_step_is_public(step: Any, public_state_ids: set[str]) -> bool:
    referenced_state_ids = [
        getattr(step, "state_id", None),
        getattr(step, "preferred_state_id", None),
        getattr(step, "alternative_state_id", None),
    ]
    return all(
        state_id in public_state_ids
        for state_id in referenced_state_ids
        if state_id is not None
    )


def _best_biology_option_id(options: list[Dict[str, Any]]) -> Optional[str]:
    candidates = [
        option for option in options
        if option["marginal_qaly"] > 0 and option["added_item_ids"]
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda option: (option["marginal_qaly"], -option["access_rank"][0], -option["access_rank"][1]),
    )["id"]


def _best_access_option_id(options: list[Dict[str, Any]]) -> Optional[str]:
    candidates = [
        option for option in options
        if option["marginal_qaly"] > 0 and option["added_item_ids"]
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda option: (
            option["access_rank"][0],
            option["access_rank"][1],
            -option["marginal_qaly"],
        ),
    )["id"]


def _round_or_none(value: Any, digits: int) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return round(number, digits)


def build_frontier_response(payload: Dict[str, Any]) -> dict[str, Any]:
    return build_frontier_response_with_policy(payload)


def build_frontier_response_with_policy(
    payload: Dict[str, Any],
    *,
    public_policy: Optional[PublicPolicy] = None,
) -> dict[str, Any]:
    profile_payload = payload.get("profile") or {}
    sleep_payload = payload.get("sleep_metrics") or {}

    weight_kg = float(profile_payload["weight_kg"])
    height_cm = float(profile_payload["height_cm"])
    sex = profile_payload.get("sex", "male")
    if sex not in ("male", "female"):
        sex = "male"

    profile = Profile(
        age=int(profile_payload["age"]),
        sex=sex,
        bmi_category=_bmi_category(weight_kg, height_cm),
        smoking_status="current" if bool(profile_payload.get("smoker")) else "never",
        has_diabetes=bool(profile_payload.get("has_diabetes")),
        has_hypertension=bool(profile_payload.get("has_hypertension")),
        activity_level=profile_payload.get("activity_level", "light"),
    )

    sleep_metrics = _build_sleep_metrics(sleep_payload)
    if sleep_metrics is None:
        duration_hours = _clean_float(profile_payload.get("sleep_hours_per_night"))
        if duration_hours is not None:
            sleep_metrics = SleepMetrics(duration_hours=duration_hours)

    n_simulations = int(payload.get("n_simulations", 5000))
    categories = payload.get("categories")

    config = AnalysisConfig(
        profile=profile,
        n_simulations=n_simulations,
        random_state=42,
        categories=categories,
        sleep_metrics=sleep_metrics,
    )

    entries = get_catalog(categories)
    analysis = analyze(config, catalog_entries=entries)

    rankable_ids = [
        item_id
        for item_id, entry in entries.items()
        if is_publicly_rankable(
            entry,
            profile=config.profile,
            sleep_estimate=config.sleep_estimate,
            policy=public_policy,
        )
    ]

    single_qalys = {
        item_id: result["total_qaly"]
        for item_id, result in analysis.item_results_by_id.items()
        if item_id in rankable_ids
    }
    annual_costs = {
        item_id: result["annual_cost"]
        for item_id, result in analysis.item_results_by_id.items()
        if item_id in rankable_ids
    }
    cost_values = {
        item_id: result["total_cost"]
        for item_id, result in analysis.item_results_by_id.items()
        if item_id in rankable_ids
    }
    exclusive_groups = {
        item_id: entry.exclusive_group
        for item_id, entry in entries.items()
        if entry.exclusive_group and item_id in rankable_ids
    }
    stack_penalty_fn = build_stack_interaction_penalty_fn(
        catalog_entries=entries,
        profile=config.profile,
        qaly_discount_rate=config.qaly_discount_rate,
        item_qalys=single_qalys,
        benefit_tag_multipliers=config.sleep_overlap_multipliers,
    )
    frontier = rank_interventions_by_marginal_cost_per_qaly(
        single_qalys=single_qalys,
        annual_costs=annual_costs,
        cost_values=cost_values,
        horizon_years=config.horizon_years,
        stack_interaction_penalty_fn=stack_penalty_fn,
        exclusive_groups=exclusive_groups,
    )

    selected_ids = set(frontier[-1]["selected_interventions"]) if frontier else set()

    items = []
    for raw in analysis.item_results:
        entry = entries[raw["id"]]
        unpriced = not is_publicly_rankable(
            entry,
            profile=config.profile,
            sleep_estimate=config.sleep_estimate,
            policy=public_policy,
        )
        _raw_ci = raw.get("net_qaly_ci", [0.0, 0.0])
        _net_qaly_ci = [round(float(_raw_ci[0]), 4), round(float(_raw_ci[1]), 4)]
        items.append({
            "id": raw["id"],
            "name": public_display_name(entry, public_policy),
            "category": entry.category,
            "display_category": public_display_category(entry, public_policy),
            "public_lane": public_recommendation_lane(entry, policy=public_policy),
            "annual_cost": None if unpriced else round(float(raw["annual_cost"]), 2),
            "total_cost": round(float(raw["total_cost"]), 2),
            "cost_per_qaly": None if unpriced else _round_or_none(raw["cost_per_qaly"], 0),
            "total_qaly": round(float(raw["total_qaly"]), 4),
            "days": round(float(raw["days"]), 1),
            "p_benefit": round(float(raw["p_benefit"]), 2),
            "p_harm": round(float(raw["p_harm"]), 2),
            "net_qaly_ci": _net_qaly_ci,
            "net_days_ci": [
                round(_net_qaly_ci[0] * 365.25, 1),
                round(_net_qaly_ci[1] * 365.25, 1),
            ],
            "mort_qaly": round(float(raw["mort_qaly"]), 4),
            "harm_qaly": round(float(raw["harm_qaly"]), 4),
            "qol_qaly": round(float(raw["qol_qaly"]), 4),
            "sleep_qol_qaly": round(float(raw["sleep_qol_qaly"]), 4),
            "profile_effect_multiplier": round(float(raw.get("profile_effect_multiplier", 1.0)), 4),
            "airway_effect_multiplier": round(float(raw.get("airway_effect_multiplier", 1.0)), 4),
            "sleep_mortality_hr_multiplier": round(float(raw.get("sleep_mortality_hr_multiplier", 1.0)), 6),
            "sleep_mortality_relief_fraction": round(float(raw.get("sleep_mortality_relief_fraction", 0.0)), 4),
            "interaction_tags": list(entry.interaction_tags),
            "benefit_tags": list(entry.benefit_tags),
            "notes": entry.notes,
            "sources": list(entry.sources),
            "selected_in_frontier": raw["id"] in selected_ids,
            "pricing_status": "unpriced" if unpriced else ("free" if raw["annual_cost"] <= 0 else "priced"),
            "rankability_reason": public_rankability_reason(
                entry,
                profile=config.profile,
                sleep_estimate=config.sleep_estimate,
                policy=public_policy,
            ),
            "access": _access_payload(entry),
        })

    items.sort(key=_sort_items)
    items_by_id = {item["id"]: item for item in items}
    public_items = [item for item in items if item["pricing_status"] != "unpriced"]

    frontier_rows = []
    for step in frontier:
        item_id = step["added_intervention"]
        item = items_by_id[item_id]
        frontier_rows.append({
            "step": step["step"],
            "added_intervention": item_id,
            "added_name": item["name"],
            "marginal_qaly": round(float(step["marginal_qaly"]), 4),
            "marginal_days": round(float(step["marginal_qaly"]) * 365.25, 1),
            "marginal_cost_per_qaly": _round_or_none(step["marginal_cost_per_qaly"], 0),
            "marginal_cost_value": round(float(step["marginal_cost_value"]), 2),
            "marginal_interaction_qaly": round(float(step["marginal_interaction_qaly"]), 4),
            "total_qaly": round(float(step["total_qaly"]), 4),
            "total_days": round(float(step["total_qaly"]) * 365.25, 1),
            "interaction_penalty_qaly": round(float(step["interaction_penalty_qaly"]), 4),
            "interaction_penalty_days": round(float(step["interaction_penalty_qaly"]) * 365.25, 1),
            "total_cost_value": round(float(step["total_cost_value"]), 2),
            "total_annual_cost": round(float(step["total_annual_cost"]), 2),
            "selected_interventions": list(step["selected_interventions"]),
        })

    def option_item_summary(item_id: str) -> Dict[str, Any]:
        item = items_by_id[item_id]
        return {
            "id": item_id,
            "name": item["name"],
            "days": item["days"],
            "annual_cost": item["annual_cost"],
            "cost_per_qaly": item["cost_per_qaly"],
            "p_benefit": item["p_benefit"],
            "p_harm": item["p_harm"],
            "access": item["access"],
        }

    decision_states = []
    decision_sequence = []
    support_signal = has_meaningful_public_airway_signal(config.sleep_estimate, policy=public_policy)
    humidifier_signal = has_meaningful_public_nasal_dryness_signal(
        config.sleep_estimate,
        policy=public_policy,
    )
    therapy_signal = has_meaningful_public_osa_therapy_signal(
        config.sleep_estimate,
        policy=public_policy,
    )
    if therapy_signal:
        support_signal = True

    if support_signal:
        decision_specs = build_public_sleep_decision_specs(
            include_therapy=therapy_signal,
            include_humidifier=humidifier_signal,
        )
        rankable_id_set = set(rankable_ids)
        decision_specs = [
            spec
            for spec in decision_specs
            if all(item_id in rankable_id_set for item_id in _decision_spec_item_ids(spec))
        ]
        public_decision_state_ids = {spec.id for spec in decision_specs}
        decision_item_ids: list[str] = []
        seen_decision_ids: set[str] = set()
        for spec in decision_specs:
            for item_id in spec.base_item_ids:
                if item_id not in seen_decision_ids:
                    decision_item_ids.append(item_id)
                    seen_decision_ids.add(item_id)
            if getattr(spec, "options", None) is None:
                continue
            for option in spec.options:
                for item_id in option.added_item_ids:
                    if item_id not in seen_decision_ids:
                        decision_item_ids.append(item_id)
                        seen_decision_ids.add(item_id)

        decision_single_qalys = {
            item_id: analysis.item_results_by_id[item_id]["total_qaly"]
            for item_id in decision_item_ids
            if item_id in analysis.item_results_by_id
        }
        decision_annual_costs = {
            item_id: analysis.item_results_by_id[item_id]["annual_cost"]
            for item_id in decision_item_ids
            if item_id in analysis.item_results_by_id
        }
        decision_cost_values = {
            item_id: analysis.item_results_by_id[item_id]["total_cost"]
            for item_id in decision_item_ids
            if item_id in analysis.item_results_by_id
        }
        decision_exclusive_groups = {
            item_id: entry.exclusive_group
            for item_id, entry in entries.items()
            if entry.exclusive_group and item_id in decision_single_qalys
        }
        raw_decision_states = evaluate_decision_states(
            decision_specs,
            single_qalys=decision_single_qalys,
            annual_costs=decision_annual_costs,
            cost_values=decision_cost_values,
            horizon_years=config.horizon_years,
            stack_interaction_penalty_fn=stack_penalty_fn,
            total_cost_value_fn=lambda ids: sum(decision_cost_values[item_id] for item_id in ids),
            exclusive_groups=decision_exclusive_groups,
        )
        serialized_states = serialize_decision_state_evaluations(
            raw_decision_states,
            item_name_by_id={item["id"]: item["name"] for item in items},
            item_summary_for_id=option_item_summary,
        )

        for spec in decision_specs:
            state_id = spec.id
            raw_state = raw_decision_states[state_id]
            serialized_state = serialized_states[state_id]
            if raw_state["kind"] == "choice":
                option_rows = []
                for option in serialized_state["options"]:
                    access = _option_access_payload(option["added_item_ids"], entries)
                    option_rows.append({
                        **option,
                        "access": access,
                        "access_rank": _access_rank(access),
                    })

                best_biology_option_id = _best_biology_option_id(option_rows)
                best_access_option_id = _best_access_option_id(option_rows)
                for option in option_rows:
                    option.pop("access_rank", None)

                decision_states.append({
                    "id": state_id,
                    "kind": "choice",
                    "label": serialized_state["label"],
                    "description": serialized_state["description"],
                    "baseline": serialized_state["baseline"],
                    "best_biology_option_id": best_biology_option_id,
                    "best_access_option_id": best_access_option_id,
                    "options": option_rows,
                })
                continue

            decision_states.append({
                "id": state_id,
                "kind": "frontier",
                "label": serialized_state["label"],
                "description": serialized_state["description"],
                "baseline": serialized_state["baseline"],
                "steps": serialized_state["steps"],
            })

        decision_sequence = serialize_decision_sequence([
            step
            for step in build_public_sleep_decision_sequence(include_therapy=therapy_signal)
            if _decision_sequence_step_is_public(step, public_decision_state_ids)
        ])

    positive_items = sum(1 for item in public_items if item["total_qaly"] > 0)
    payload_out = {
        "meta": {
            "selection_mode": "ordered_by_marginal_cost_per_qaly",
            "analyzed_count": len(items),
            "positive_count": positive_items,
            "qaly_discount_rate": config.qaly_discount_rate,
            "cost_discount_rate": config.cost_discount_rate,
            "n_simulations": config.n_simulations,
            "rankable_count": len(rankable_ids),
            "profile": {
                "age": profile.age,
                "sex": profile.sex,
                "bmi_category": profile.bmi_category,
                "smoking_status": profile.smoking_status,
                "has_diabetes": profile.has_diabetes,
                "has_hypertension": profile.has_hypertension,
                "activity_level": profile.activity_level,
            },
        },
        "sleep_estimate": None,
        "public_policy": build_public_policy_spec(entries, policy=public_policy),
        "frontier": frontier_rows,
        "items": public_items,
        "decision_states": decision_states,
        "decision_sequence": decision_sequence,
    }

    if config.sleep_estimate is not None:
        payload_out["sleep_estimate"] = {
            "annual_qaly_loss": round(float(config.sleep_estimate.annual_qaly_loss), 4),
            "mortality_signal": round(float(config.sleep_estimate.mortality_signal), 4),
            "component_losses": {
                key: round(float(value), 4)
                for key, value in config.sleep_estimate.component_losses.items()
            },
            "component_burdens": {
                key: round(float(value), 3)
                for key, value in config.sleep_estimate.component_burdens.items()
            },
            "airway": (
                {
                    "upper_airway_probability": round(float(config.sleep_estimate.airway.upper_airway_probability), 3),
                    "nasal_inflammation_probability": round(float(config.sleep_estimate.airway.nasal_inflammation_probability), 3),
                    "mucus_probability": round(float(config.sleep_estimate.airway.mucus_probability), 3),
                    "response_signal": round(float(config.sleep_estimate.airway.response_signal), 3),
                }
                if config.sleep_estimate.airway is not None
                else None
            ),
        }

    return payload_out
