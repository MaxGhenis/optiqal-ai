"""Benchmark harness for public-frontier plausibility and safety."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import random
from typing import Any, Literal, Optional

from .catalog import (
    PublicPolicy,
    has_meaningful_public_airway_signal,
    has_meaningful_public_nasal_dryness_signal,
    has_meaningful_public_osa_therapy_signal,
)
from .sleep import SleepMetrics, estimate_sleep_burden
from .web_api import build_frontier_response_with_policy


BENCHMARK_SCENARIOS_PATH = Path(__file__).parent / "data" / "public_frontier_benchmark_scenarios.json"
JUDGE_PROMPT_TEMPLATE_PATH = Path(__file__).parent / "data" / "public_frontier_judge_prompt.md"


@dataclass(frozen=True)
class PublicFrontierBenchmarkRules:
    """Hard rules for one benchmark scenario."""

    top_n: int = 10
    banned_top_ids: tuple[str, ...] = ()
    banned_visible_ids: tuple[str, ...] = ()
    required_top_any_of: tuple[str, ...] = ()
    required_visible_ids: tuple[str, ...] = ()
    required_visible_order: tuple[tuple[str, str], ...] = ()
    required_decision_state_ids: tuple[str, ...] = ()
    banned_decision_state_ids: tuple[str, ...] = ()
    forbidden_visible_pairs: tuple[tuple[str, str], ...] = ()
    expected_airway_decision_states: Optional[bool] = None


@dataclass(frozen=True)
class PublicFrontierBenchmarkScenario:
    """Single scenario to evaluate against the public frontier."""

    id: str
    label: str
    description: str
    payload: dict[str, Any]
    rules: PublicFrontierBenchmarkRules
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class PublicFrontierBenchmarkFailure:
    """One hard-rule failure for a scenario."""

    rule: str
    message: str


@dataclass(frozen=True)
class PublicFrontierBenchmarkCaseResult:
    """Scored output for one scenario."""

    scenario_id: str
    label: str
    passed: bool
    checks_run: int
    checks_failed: int
    score: float
    failures: tuple[PublicFrontierBenchmarkFailure, ...]
    frontier_ids: tuple[str, ...]
    top_ids: tuple[str, ...]
    airway_decision_states_present: bool
    response: dict[str, Any]


@dataclass(frozen=True)
class PublicFrontierBenchmarkReport:
    """Aggregate benchmark report across scenarios."""

    case_results: tuple[PublicFrontierBenchmarkCaseResult, ...]
    total_checks: int
    total_failures: int
    score: float


@dataclass(frozen=True)
class PublicFrontierJudgePacket:
    """Pairwise prompt packet for one scenario."""

    scenario_id: str
    label: str
    prompt: str
    candidate_a_summary: dict[str, Any]
    candidate_b_summary: dict[str, Any]


@dataclass(frozen=True)
class PublicFrontierJudgeVerdict:
    """Structured offline verdict from an LLM judge."""

    scenario_id: str
    winner: Literal["A", "B", "tie"]
    confidence: float
    summary: str
    safety_issues: tuple[str, ...] = ()
    ranking_issues: tuple[str, ...] = ()
    best_aspects_a: tuple[str, ...] = ()
    best_aspects_b: tuple[str, ...] = ()


PairwiseJudgePacketMode = Literal["all", "changed", "changed_unique"]


def _load_benchmark_scenarios() -> tuple[PublicFrontierBenchmarkScenario, ...]:
    raw_cases = json.loads(BENCHMARK_SCENARIOS_PATH.read_text())
    scenarios: list[PublicFrontierBenchmarkScenario] = []

    for raw_case in raw_cases:
        rules = raw_case["rules"]
        scenarios.append(
            PublicFrontierBenchmarkScenario(
                id=str(raw_case["id"]),
                label=str(raw_case["label"]),
                description=str(raw_case["description"]),
                payload=dict(raw_case["payload"]),
                rules=PublicFrontierBenchmarkRules(
                    top_n=int(rules.get("top_n", 10)),
                    banned_top_ids=tuple(rules.get("banned_top_ids", [])),
                    banned_visible_ids=tuple(rules.get("banned_visible_ids", [])),
                    required_top_any_of=tuple(rules.get("required_top_any_of", [])),
                    required_visible_ids=tuple(rules.get("required_visible_ids", [])),
                    required_visible_order=tuple(
                        tuple(pair) for pair in rules.get("required_visible_order", [])
                    ),
                    required_decision_state_ids=tuple(rules.get("required_decision_state_ids", [])),
                    banned_decision_state_ids=tuple(rules.get("banned_decision_state_ids", [])),
                    forbidden_visible_pairs=tuple(
                        tuple(pair) for pair in rules.get("forbidden_visible_pairs", [])
                    ),
                    expected_airway_decision_states=rules.get("expected_airway_decision_states"),
                ),
                tags=tuple(raw_case.get("tags", [])),
            )
        )

    return tuple(scenarios)


CANONICAL_PUBLIC_FRONTIER_SCENARIOS = _load_benchmark_scenarios()


def _healthy_payload(rng: random.Random, *, sex: str) -> dict[str, Any]:
    height_cm = rng.choice([165, 170, 175, 178])
    weight_kg = rng.choice([60, 65, 70, 74])
    return {
        "profile": {
            "age": rng.choice([28, 32, 35, 38]),
            "sex": sex,
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": False,
            "activity_level": rng.choice(["light", "active"]),
            "sleep_hours_per_night": rng.choice([7, 7.5]),
        },
        "n_simulations": 1000,
    }


def _cardiometabolic_payload(rng: random.Random) -> dict[str, Any]:
    height_cm, weight_kg = rng.choice(
        [
            (165, 95),
            (175, 102),
            (180, 110),
        ]
    )
    return {
        "profile": {
            "age": rng.choice([54, 58, 62]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "smoker": rng.choice([True, False]),
            "has_diabetes": False,
            "has_hypertension": True,
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _glp1_payload(rng: random.Random) -> dict[str, Any]:
    return {
        "profile": {
            "age": rng.choice([48, 52, 57]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": rng.choice([100, 106, 114]),
            "height_cm": rng.choice([165, 170, 175]),
            "smoker": False,
            "has_diabetes": True,
            "has_hypertension": rng.choice([True, False]),
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _borderline_metabolic_payload(rng: random.Random) -> dict[str, Any]:
    height_cm, weight_kg = rng.choice(
        [
            (172, 84),
            (178, 88),
            (182, 92),
        ]
    )
    return {
        "profile": {
            "age": rng.choice([50, 52, 55]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": True,
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _obesity_glp1_no_diabetes_payload(rng: random.Random) -> dict[str, Any]:
    return {
        "profile": {
            "age": rng.choice([50, 52, 56]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": rng.choice([100, 106, 112]),
            "height_cm": rng.choice([162, 168, 175]),
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": True,
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _severe_obesity_no_comorbidity_payload(rng: random.Random) -> dict[str, Any]:
    return {
        "profile": {
            "age": rng.choice([42, 46, 52, 58]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": rng.choice([110, 116, 124]),
            "height_cm": rng.choice([160, 165, 170]),
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": False,
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _older_obesity_no_comorbidity_payload(rng: random.Random) -> dict[str, Any]:
    return {
        "profile": {
            "age": rng.choice([62, 66, 70]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": rng.choice([96, 100, 102]),
            "height_cm": rng.choice([172, 175, 178]),
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": False,
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _lean_diabetes_younger_payload(rng: random.Random) -> dict[str, Any]:
    height_cm, weight_kg = rng.choice(
        [
            (172, 68),
            (178, 72),
            (182, 76),
        ]
    )
    return {
        "profile": {
            "age": rng.choice([40, 45, 48]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "smoker": False,
            "has_diabetes": True,
            "has_hypertension": False,
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _lean_diabetes_older_payload(rng: random.Random) -> dict[str, Any]:
    height_cm, weight_kg = rng.choice(
        [
            (172, 68),
            (178, 72),
            (182, 76),
        ]
    )
    return {
        "profile": {
            "age": rng.choice([50, 52, 55]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": weight_kg,
            "height_cm": height_cm,
            "smoker": False,
            "has_diabetes": True,
            "has_hypertension": False,
            "activity_level": "light",
            "sleep_hours_per_night": 7,
        },
        "n_simulations": 1000,
    }


def _airway_payload(rng: random.Random) -> dict[str, Any]:
    return {
        "profile": {
            "age": rng.choice([37, 39, 42]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": rng.choice([70, 74.8, 82]),
            "height_cm": rng.choice([168, 175, 178]),
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": False,
            "activity_level": rng.choice(["light", "active"]),
            "sleep_hours_per_night": rng.choice([6.6, 6.8, 7.0]),
        },
        "sleep_metrics": {
            "duration_hours": rng.choice([6.6, 6.8, 7.0]),
            "breathing_score": rng.choice([0.74, 0.78, 0.82]),
            "spo2": rng.choice([94.8, 95.1, 95.5]),
            "snore_pct": rng.choice([2.5, 3.2, 4.4]),
            "airway_response_signal": rng.choice([0.35, 0.4, 0.5]),
        },
        "n_simulations": 1000,
    }


def _duration_only_payload(rng: random.Random) -> dict[str, Any]:
    return {
        "profile": {
            "age": rng.choice([37, 39, 42]),
            "sex": rng.choice(["male", "female"]),
            "weight_kg": rng.choice([70, 74.8, 82]),
            "height_cm": rng.choice([168, 175, 178]),
            "smoker": False,
            "has_diabetes": False,
            "has_hypertension": False,
            "activity_level": rng.choice(["light", "active"]),
            "sleep_hours_per_night": rng.choice([5.8, 6.0, 6.2]),
        },
        "sleep_metrics": {
            "duration_hours": rng.choice([5.8, 6.0, 6.2]),
            "sleep_quality_score": rng.choice([74, 78, 82]),
            "routine_score": rng.choice([70, 72, 76]),
        },
        "n_simulations": 1000,
    }


def _nasal_support_only_payload(rng: random.Random) -> dict[str, Any]:
    for _ in range(64):
        payload = {
            "profile": {
                "age": rng.choice([37, 39, 42]),
                "sex": rng.choice(["male", "female"]),
                "weight_kg": rng.choice([70, 74.8, 82]),
                "height_cm": rng.choice([168, 175, 178]),
                "smoker": False,
                "has_diabetes": False,
                "has_hypertension": False,
                "activity_level": rng.choice(["light", "active"]),
                "sleep_hours_per_night": rng.choice([6.6, 6.8, 7.0]),
            },
            "sleep_metrics": {
                "duration_hours": rng.choice([6.6, 6.8, 7.0]),
                "breathing_score": rng.choice([0.74, 0.76, 0.78]),
                "spo2": rng.choice([95.6, 95.7]),
                "snore_pct": rng.choice([0.8, 1.0]),
                "airway_response_signal": rng.choice([0.05, 0.06]),
            },
            "n_simulations": 1000,
        }
        estimate = estimate_sleep_burden(SleepMetrics(**payload["sleep_metrics"]))
        if (
            has_meaningful_public_airway_signal(estimate)
            and not has_meaningful_public_osa_therapy_signal(estimate)
            and not has_meaningful_public_nasal_dryness_signal(estimate)
        ):
            return payload

    raise RuntimeError("Could not generate a support-only sleep benchmark payload that matches policy semantics.")


def generate_stratified_public_frontier_scenarios(
    *,
    seed: int = 42,
    cases_per_stratum: int = 1,
) -> tuple[PublicFrontierBenchmarkScenario, ...]:
    """Generate extra benchmark scenarios across key public-product strata."""
    rng = random.Random(seed)
    scenarios: list[PublicFrontierBenchmarkScenario] = []

    strata = [
        (
            "healthy_public",
            lambda: _healthy_payload(rng, sex=rng.choice(["male", "female"])),
            PublicFrontierBenchmarkRules(
                top_n=10,
                banned_top_ids=(
                    "aspirin_81mg",
                    "finasteride_1.25mg",
                    "tadalafil_2.5mg",
                    "head_elevation_nightly",
                    "statin_5mg",
                    "metformin_500mg",
                    "semaglutide",
                ),
                banned_visible_ids=("apap_nightly", "oral_appliance_custom"),
                required_top_any_of=("hiit_2x_week", "strength_maintenance"),
                forbidden_visible_pairs=(("finasteride_1.25mg", "tadalafil_2.5mg"),),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "cardiometabolic_public",
            lambda: _cardiometabolic_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("statin_5mg", "semaglutide"),
                required_visible_order=(("statin_5mg", "metformin_500mg"),),
                banned_visible_ids=("metformin_500mg", "finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "glp1_public",
            lambda: _glp1_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("semaglutide", "metformin_500mg"),
                required_visible_order=(
                    ("metformin_500mg", "semaglutide"),
                    ("statin_5mg", "semaglutide"),
                ),
                banned_visible_ids=("finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "borderline_metabolic_public",
            lambda: _borderline_metabolic_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("statin_5mg",),
                required_visible_order=(("statin_5mg", "metformin_500mg"),),
                banned_visible_ids=("metformin_500mg", "semaglutide", "finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "obesity_glp1_no_diabetes_public",
            lambda: _obesity_glp1_no_diabetes_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("statin_5mg", "semaglutide"),
                required_visible_order=(
                    ("statin_5mg", "metformin_500mg"),
                    ("semaglutide", "metformin_500mg"),
                ),
                banned_visible_ids=("metformin_500mg", "finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "severe_obesity_public",
            lambda: _severe_obesity_no_comorbidity_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("semaglutide",),
                banned_visible_ids=("metformin_500mg", "statin_5mg", "finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "older_obesity_public",
            lambda: _older_obesity_no_comorbidity_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("semaglutide",),
                banned_visible_ids=("metformin_500mg", "finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "lean_diabetes_younger_public",
            lambda: _lean_diabetes_younger_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("statin_5mg", "metformin_500mg"),
                required_visible_order=(("metformin_500mg", "statin_5mg"),),
                banned_visible_ids=("semaglutide", "finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "lean_diabetes_older_public",
            lambda: _lean_diabetes_older_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("statin_5mg", "metformin_500mg"),
                required_visible_order=(("metformin_500mg", "statin_5mg"),),
                banned_visible_ids=("semaglutide", "finasteride_1.25mg", "tadalafil_2.5mg"),
                expected_airway_decision_states=False,
            ),
        ),
        (
            "airway_sleep",
            lambda: _airway_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=15,
                required_visible_ids=("apap_nightly", "head_elevation_nightly"),
                banned_visible_ids=("finasteride_1.25mg", "tadalafil_2.5mg", "mouth_tape_nightly"),
                expected_airway_decision_states=True,
            ),
        ),
        (
            "nasal_support_only_sleep",
            lambda: _nasal_support_only_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                required_visible_ids=("head_elevation_nightly", "nasacort_nightly"),
                required_visible_order=(
                    ("head_elevation_nightly", "nasal_strips_nightly"),
                    ("nasacort_nightly", "nasal_strips_nightly"),
                ),
                banned_visible_ids=(
                    "apap_nightly",
                    "oral_appliance_custom",
                    "humidifier_nightly",
                    "mouth_tape_nightly",
                ),
                required_decision_state_ids=("conservative_airway_support",),
                banned_decision_state_ids=(
                    "primary_osa_therapy_choice",
                    "rx_after_apap_if_needed",
                    "rx_after_oral_appliance_if_needed",
                ),
                expected_airway_decision_states=True,
            ),
        ),
        (
            "duration_only_sleep",
            lambda: _duration_only_payload(rng),
            PublicFrontierBenchmarkRules(
                top_n=12,
                banned_visible_ids=("apap_nightly", "oral_appliance_custom", "head_elevation_nightly"),
                expected_airway_decision_states=False,
            ),
        ),
    ]

    for stratum_id, payload_factory, rules in strata:
        for index in range(cases_per_stratum):
            scenarios.append(
                PublicFrontierBenchmarkScenario(
                    id=f"{stratum_id}_{index + 1}",
                    label=stratum_id.replace("_", " "),
                    description=f"Generated {stratum_id} benchmark case.",
                    payload=payload_factory(),
                    rules=rules,
                    tags=(stratum_id, "generated"),
                )
            )

    return tuple(scenarios)


def build_public_frontier_benchmark_scenarios(
    *,
    cases_per_stratum: int = 0,
    seed: int = 42,
    seed_count: int = 1,
    include_canonical: bool = True,
) -> tuple[PublicFrontierBenchmarkScenario, ...]:
    """Build a benchmark scenario set, optionally spanning multiple generation seeds."""
    if seed_count < 1:
        raise ValueError("seed_count must be at least 1")

    scenarios: list[PublicFrontierBenchmarkScenario] = []
    if include_canonical:
        scenarios.extend(CANONICAL_PUBLIC_FRONTIER_SCENARIOS)

    if cases_per_stratum <= 0:
        return tuple(scenarios)

    for seed_offset in range(seed_count):
        active_seed = seed + seed_offset
        generated = generate_stratified_public_frontier_scenarios(
            seed=active_seed,
            cases_per_stratum=cases_per_stratum,
        )
        for scenario in generated:
            scenarios.append(
                PublicFrontierBenchmarkScenario(
                    id=f"seed{active_seed}__{scenario.id}",
                    label=f"{scenario.label} [seed {active_seed}]",
                    description=f"{scenario.description} Seed {active_seed}.",
                    payload=scenario.payload,
                    rules=scenario.rules,
                    tags=(*scenario.tags, f"seed:{active_seed}"),
                )
            )

    return tuple(scenarios)


def evaluate_public_frontier_case(
    scenario: PublicFrontierBenchmarkScenario,
    *,
    public_policy: Optional[PublicPolicy] = None,
) -> PublicFrontierBenchmarkCaseResult:
    """Run one scenario through the public frontier and score hard rules."""
    response = build_frontier_response_with_policy(
        scenario.payload,
        public_policy=public_policy,
    )
    frontier_ids = tuple(row["added_intervention"] for row in response["frontier"])
    top_ids = frontier_ids[: scenario.rules.top_n]
    decision_state_ids = tuple(state["id"] for state in response["decision_states"])
    failures: list[PublicFrontierBenchmarkFailure] = []
    checks_run = 0

    for item_id in scenario.rules.banned_top_ids:
        checks_run += 1
        if item_id in top_ids:
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="banned_top_ids",
                    message=f"{item_id} appeared in the top {scenario.rules.top_n}.",
                )
            )

    for item_id in scenario.rules.banned_visible_ids:
        checks_run += 1
        if item_id in frontier_ids:
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="banned_visible_ids",
                    message=f"{item_id} appeared anywhere in the visible frontier.",
                )
            )

    if scenario.rules.required_top_any_of:
        checks_run += 1
        if not any(item_id in top_ids for item_id in scenario.rules.required_top_any_of):
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="required_top_any_of",
                    message=(
                        "None of the required broad-public items appeared in the top "
                        f"{scenario.rules.top_n}: {list(scenario.rules.required_top_any_of)}"
                    ),
                )
            )

    for item_id in scenario.rules.required_visible_ids:
        checks_run += 1
        if item_id not in frontier_ids:
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="required_visible_ids",
                    message=f"{item_id} did not appear in the visible frontier.",
                )
            )

    for left_id, right_id in scenario.rules.required_visible_order:
        checks_run += 1
        if left_id in frontier_ids and right_id in frontier_ids:
            if frontier_ids.index(left_id) > frontier_ids.index(right_id):
                failures.append(
                    PublicFrontierBenchmarkFailure(
                        rule="required_visible_order",
                        message=(
                            f"{left_id} must rank ahead of {right_id} in the visible frontier."
                        ),
                    )
                )

    for state_id in scenario.rules.required_decision_state_ids:
        checks_run += 1
        if state_id not in decision_state_ids:
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="required_decision_state_ids",
                    message=f"{state_id} did not appear in the decision states.",
                )
            )

    for state_id in scenario.rules.banned_decision_state_ids:
        checks_run += 1
        if state_id in decision_state_ids:
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="banned_decision_state_ids",
                    message=f"{state_id} appeared in the decision states.",
                )
            )

    for left_id, right_id in scenario.rules.forbidden_visible_pairs:
        checks_run += 1
        if left_id in frontier_ids and right_id in frontier_ids:
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="forbidden_visible_pairs",
                    message=f"{left_id} and {right_id} both appeared in the same visible frontier.",
                )
            )

    airway_states_present = bool(response["decision_states"])
    if scenario.rules.expected_airway_decision_states is not None:
        checks_run += 1
        if airway_states_present != scenario.rules.expected_airway_decision_states:
            failures.append(
                PublicFrontierBenchmarkFailure(
                    rule="expected_airway_decision_states",
                    message=(
                        "Airway decision-state presence mismatch: "
                        f"expected {scenario.rules.expected_airway_decision_states}, got {airway_states_present}."
                    ),
                )
            )

    checks_failed = len(failures)
    score = 1.0 if checks_run == 0 else max(0.0, (checks_run - checks_failed) / checks_run)

    return PublicFrontierBenchmarkCaseResult(
        scenario_id=scenario.id,
        label=scenario.label,
        passed=checks_failed == 0,
        checks_run=checks_run,
        checks_failed=checks_failed,
        score=score,
        failures=tuple(failures),
        frontier_ids=frontier_ids,
        top_ids=top_ids,
        airway_decision_states_present=airway_states_present,
        response=response,
    )


def run_public_frontier_benchmark(
    scenarios: Optional[tuple[PublicFrontierBenchmarkScenario, ...]] = None,
    *,
    public_policy: Optional[PublicPolicy] = None,
) -> PublicFrontierBenchmarkReport:
    """Run the canonical or provided benchmark scenario set."""
    active_scenarios = scenarios or CANONICAL_PUBLIC_FRONTIER_SCENARIOS
    case_results = tuple(
        evaluate_public_frontier_case(scenario, public_policy=public_policy)
        for scenario in active_scenarios
    )
    total_checks = sum(result.checks_run for result in case_results)
    total_failures = sum(result.checks_failed for result in case_results)
    score = 1.0 if total_checks == 0 else max(0.0, (total_checks - total_failures) / total_checks)
    return PublicFrontierBenchmarkReport(
        case_results=case_results,
        total_checks=total_checks,
        total_failures=total_failures,
        score=score,
    )


def benchmark_report_to_dict(
    report: PublicFrontierBenchmarkReport,
    *,
    include_responses: bool = True,
) -> dict[str, Any]:
    """Serialize a benchmark report for storage or later pairwise review."""
    return {
        "score": report.score,
        "total_checks": report.total_checks,
        "total_failures": report.total_failures,
        "cases": [
            {
                "scenario_id": result.scenario_id,
                "label": result.label,
                "passed": result.passed,
                "score": result.score,
                "checks_run": result.checks_run,
                "checks_failed": result.checks_failed,
                "frontier_ids": list(result.frontier_ids),
                "top_ids": list(result.top_ids),
                "airway_decision_states_present": result.airway_decision_states_present,
                "failures": [
                    {"rule": failure.rule, "message": failure.message}
                    for failure in result.failures
                ],
                "response": result.response if include_responses else None,
            }
            for result in report.case_results
        ],
    }


def benchmark_report_from_dict(payload: dict[str, Any]) -> PublicFrontierBenchmarkReport:
    """Deserialize a stored benchmark report."""
    case_results = []
    for raw_case in payload.get("cases", []):
        case_results.append(
            PublicFrontierBenchmarkCaseResult(
                scenario_id=str(raw_case["scenario_id"]),
                label=str(raw_case["label"]),
                passed=bool(raw_case["passed"]),
                checks_run=int(raw_case["checks_run"]),
                checks_failed=int(raw_case["checks_failed"]),
                score=float(raw_case["score"]),
                failures=tuple(
                    PublicFrontierBenchmarkFailure(
                        rule=str(failure["rule"]),
                        message=str(failure["message"]),
                    )
                    for failure in raw_case.get("failures", [])
                ),
                frontier_ids=tuple(raw_case.get("frontier_ids", [])),
                top_ids=tuple(raw_case.get("top_ids", [])),
                airway_decision_states_present=bool(raw_case.get("airway_decision_states_present", False)),
                response=dict(raw_case["response"] or {}),
            )
        )

    return PublicFrontierBenchmarkReport(
        case_results=tuple(case_results),
        total_checks=int(payload["total_checks"]),
        total_failures=int(payload["total_failures"]),
        score=float(payload["score"]),
    )


def _candidate_summary(response: dict[str, Any]) -> dict[str, Any]:
    frontier_rows = response["frontier"][:10]
    return {
        "profile": response["meta"]["profile"],
        "frontier_top_10": [
            {
                "rank": index + 1,
                "id": row["added_intervention"],
                "name": row["added_name"],
                "marginal_days": row["marginal_days"],
                "marginal_cost_per_qaly": row["marginal_cost_per_qaly"],
            }
            for index, row in enumerate(frontier_rows)
        ],
        "decision_state_ids": [state["id"] for state in response["decision_states"]],
    }


def _scenario_rules_signature(scenario: PublicFrontierBenchmarkScenario) -> tuple[Any, ...]:
    return (
        scenario.rules.top_n,
        scenario.rules.banned_top_ids,
        scenario.rules.banned_visible_ids,
        scenario.rules.required_top_any_of,
        scenario.rules.required_visible_ids,
        scenario.rules.required_visible_order,
        scenario.rules.required_decision_state_ids,
        scenario.rules.banned_decision_state_ids,
        scenario.rules.forbidden_visible_pairs,
        scenario.rules.expected_airway_decision_states,
    )


def _case_diff_signature(
    case_a: PublicFrontierBenchmarkCaseResult,
    case_b: PublicFrontierBenchmarkCaseResult,
    scenario: PublicFrontierBenchmarkScenario,
) -> tuple[Any, ...]:
    return (
        round(case_a.score, 6),
        round(case_b.score, 6),
        case_a.top_ids,
        case_b.top_ids,
        tuple((failure.rule, failure.message) for failure in case_a.failures),
        tuple((failure.rule, failure.message) for failure in case_b.failures),
        _scenario_rules_signature(scenario),
    )


def _cases_differ(
    case_a: PublicFrontierBenchmarkCaseResult,
    case_b: PublicFrontierBenchmarkCaseResult,
) -> bool:
    return (
        case_a.score != case_b.score
        or case_a.top_ids != case_b.top_ids
        or case_a.failures != case_b.failures
        or case_a.airway_decision_states_present != case_b.airway_decision_states_present
    )


def render_public_frontier_judge_prompt(
    scenario: PublicFrontierBenchmarkScenario,
    candidate_a_response: dict[str, Any],
    candidate_b_response: dict[str, Any],
) -> str:
    """Render a pairwise LLM judge prompt for one scenario."""
    template = JUDGE_PROMPT_TEMPLATE_PATH.read_text()
    return (
        template
        .replace("{{scenario}}", json.dumps({
            "id": scenario.id,
            "label": scenario.label,
            "description": scenario.description,
            "tags": list(scenario.tags),
            "rules": {
                "top_n": scenario.rules.top_n,
                "banned_top_ids": list(scenario.rules.banned_top_ids),
                "banned_visible_ids": list(scenario.rules.banned_visible_ids),
                "required_top_any_of": list(scenario.rules.required_top_any_of),
                "required_visible_ids": list(scenario.rules.required_visible_ids),
                "required_visible_order": [list(pair) for pair in scenario.rules.required_visible_order],
                "required_decision_state_ids": list(scenario.rules.required_decision_state_ids),
                "banned_decision_state_ids": list(scenario.rules.banned_decision_state_ids),
                "forbidden_visible_pairs": [list(pair) for pair in scenario.rules.forbidden_visible_pairs],
                "expected_airway_decision_states": scenario.rules.expected_airway_decision_states,
            },
        }, indent=2))
        .replace("{{candidate_a}}", json.dumps(_candidate_summary(candidate_a_response), indent=2))
        .replace("{{candidate_b}}", json.dumps(_candidate_summary(candidate_b_response), indent=2))
    )


def build_pairwise_judge_packets(
    candidate_a_report: PublicFrontierBenchmarkReport,
    candidate_b_report: PublicFrontierBenchmarkReport,
    *,
    scenarios: Optional[tuple[PublicFrontierBenchmarkScenario, ...]] = None,
    mode: PairwiseJudgePacketMode = "all",
) -> tuple[PublicFrontierJudgePacket, ...]:
    """Build pairwise judge packets comparing candidate A vs B on matching scenarios."""
    active_scenarios = scenarios or CANONICAL_PUBLIC_FRONTIER_SCENARIOS
    candidate_a_cases = {result.scenario_id: result for result in candidate_a_report.case_results}
    candidate_b_cases = {result.scenario_id: result for result in candidate_b_report.case_results}

    packets = []
    seen_signatures: set[tuple[Any, ...]] = set()
    for scenario in active_scenarios:
        scenario_id = scenario.id
        if scenario_id not in candidate_a_cases or scenario_id not in candidate_b_cases:
            continue
        case_a = candidate_a_cases[scenario_id]
        case_b = candidate_b_cases[scenario_id]
        if mode != "all":
            changed = _cases_differ(case_a, case_b)
            if not changed:
                continue
            if mode == "changed_unique":
                signature = _case_diff_signature(case_a, case_b, scenario)
                is_public_canary = "public_canary" in scenario.tags
                if not is_public_canary and signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
        if not case_a.response or not case_b.response:
            raise ValueError(
                f"Pairwise judge packets require stored responses for scenario {scenario_id}."
            )
        packets.append(
            PublicFrontierJudgePacket(
                scenario_id=scenario_id,
                label=scenario.label,
                prompt=render_public_frontier_judge_prompt(
                    scenario,
                    case_a.response,
                    case_b.response,
                ),
                candidate_a_summary=_candidate_summary(case_a.response),
                candidate_b_summary=_candidate_summary(case_b.response),
            )
        )

    return tuple(packets)


def build_blank_judge_verdict_template(
    packets: tuple[PublicFrontierJudgePacket, ...],
) -> list[dict[str, Any]]:
    """Create a fill-in template for offline pairwise judge verdicts."""
    return [
        {
            "scenario_id": packet.scenario_id,
            "label": packet.label,
            "winner": "A|B|tie",
            "confidence": 0.5,
            "summary": "",
            "safety_issues": [],
            "ranking_issues": [],
            "best_aspects": {
                "A": [],
                "B": [],
            },
        }
        for packet in packets
    ]


def judge_packet_to_dict(packet: PublicFrontierJudgePacket) -> dict[str, Any]:
    """Serialize one pairwise judge packet."""
    return {
        "scenario_id": packet.scenario_id,
        "label": packet.label,
        "prompt": packet.prompt,
        "candidate_a_summary": packet.candidate_a_summary,
        "candidate_b_summary": packet.candidate_b_summary,
    }


def parse_public_frontier_judge_verdicts(
    payload: list[dict[str, Any]],
) -> tuple[PublicFrontierJudgeVerdict, ...]:
    """Parse stored offline judge verdicts."""
    verdicts = []
    for raw_verdict in payload:
        winner = raw_verdict["winner"]
        if winner not in {"A", "B", "tie"}:
            raise ValueError(f"Unexpected judge winner: {winner}")
        verdicts.append(
            PublicFrontierJudgeVerdict(
                scenario_id=str(raw_verdict["scenario_id"]),
                winner=winner,
                confidence=float(raw_verdict["confidence"]),
                summary=str(raw_verdict["summary"]),
                safety_issues=tuple(raw_verdict.get("safety_issues", [])),
                ranking_issues=tuple(raw_verdict.get("ranking_issues", [])),
                best_aspects_a=tuple((raw_verdict.get("best_aspects") or {}).get("A", [])),
                best_aspects_b=tuple((raw_verdict.get("best_aspects") or {}).get("B", [])),
            )
        )
    return tuple(verdicts)


def compute_pairwise_judge_score(
    verdicts: tuple[PublicFrontierJudgeVerdict, ...],
) -> float:
    """Score candidate A preference from offline judge verdicts."""
    if not verdicts:
        return 0.5

    weighted_total = 0.0
    weight_sum = 0.0
    for verdict in verdicts:
        weight = max(0.0, min(1.0, verdict.confidence))
        if verdict.winner == "A":
            points = 1.0
        elif verdict.winner == "B":
            points = 0.0
        else:
            points = 0.5
        weighted_total += points * weight
        weight_sum += weight

    if weight_sum == 0:
        return 0.5
    return weighted_total / weight_sum


def compute_hybrid_public_frontier_score(
    *,
    hard_score: float,
    judge_score: Optional[float],
    judge_weight: float = 0.2,
) -> float:
    """Combine hard benchmark score with optional judge preference score.

    Hard-rule failures dominate. The judge only matters once the hard benchmark is perfect.
    """
    if hard_score < 1.0 or judge_score is None:
        return hard_score

    bounded_weight = max(0.0, min(1.0, judge_weight))
    return (1.0 - bounded_weight) * hard_score + bounded_weight * judge_score
