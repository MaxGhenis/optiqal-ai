#!/usr/bin/env python3
"""Task-local single-file public-policy harness for Harbor/AutoAgent benchmarks."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from optiqal import load_public_policy_override
from optiqal.public_frontier_benchmark import (
    benchmark_report_to_dict,
    build_blank_judge_verdict_template,
    build_public_frontier_benchmark_scenarios,
    build_pairwise_judge_packets,
    compute_hybrid_public_frontier_score,
    compute_pairwise_judge_score,
    judge_packet_to_dict,
    parse_public_frontier_judge_verdicts,
    run_public_frontier_benchmark,
)


DEFAULT_JUDGE_VERDICTS_ENV = "PUBLIC_FRONTIER_JUDGE_VERDICTS"


# ---------------------------------------------------------------------------
# Editable policy section
# ---------------------------------------------------------------------------

CANDIDATE_POLICY: dict[str, Any] = {
    "lanes": {},
    "conditions": {
        "cardiometabolic_signal": {
            "profile_score_threshold": 4,
            "profile_rules": [
                {"field": "age", "operator": "gte", "value": 60, "points": 2, "label": "Age 60+"},
                {"field": "age", "operator": "gte", "value": 50, "points": 1, "label": "Age 50+"},
                {"field": "bmi_category", "operator": "eq", "value": "overweight", "points": 1, "label": "BMI in overweight range"},
                {"field": "bmi_category", "operator": "in", "value": ["obese", "severely_obese"], "points": 2, "label": "BMI in obese range"},
                {"field": "smoking_status", "operator": "eq", "value": "current", "points": 2, "label": "Current smoker"},
                {"field": "has_hypertension", "operator": "eq", "value": True, "points": 2, "label": "Has hypertension"},
                {"field": "has_diabetes", "operator": "eq", "value": True, "points": 4, "label": "Has diabetes"},
            ],
        },
        "metabolic_signal": {
            "profile_score_threshold": 5,
            "profile_rules": [
                {"field": "has_diabetes", "operator": "eq", "value": True, "points": 5, "label": "Has diabetes"},
                {"field": "bmi_category", "operator": "eq", "value": "overweight", "points": 1, "label": "BMI in overweight range"},
                {"field": "bmi_category", "operator": "in", "value": ["obese", "severely_obese"], "points": 2, "label": "BMI in obese range"},
                {"field": "has_hypertension", "operator": "eq", "value": True, "points": 1, "label": "Has hypertension"},
                {"field": "age", "operator": "gte", "value": 50, "points": 1, "label": "Age 50+"},
            ],
        },
        "glp1_signal": {
            "profile_score_threshold": 5,
            "profile_rules": [
                {"field": "has_diabetes", "operator": "eq", "value": True, "points": 3, "label": "Has diabetes"},
                {"field": "bmi_category", "operator": "eq", "value": "overweight", "points": 1, "label": "BMI in overweight range"},
                {"field": "bmi_category", "operator": "in", "value": ["obese", "severely_obese"], "points": 3, "label": "BMI in obese range"},
                {"field": "has_hypertension", "operator": "eq", "value": True, "points": 1, "label": "Has hypertension"},
                {"field": "age", "operator": "gte", "value": 50, "points": 1, "label": "Age 50+"},
            ],
        },
    },
    "items": {
        "statin_5mg": {
            "public_lane": "conditional_public",
            "public_condition": "cardiometabolic_signal",
            "public_display_category_override": "rx",
        },
    },
    "excluded_reasons": {
        "vitamin_d_2000": None,
    },
}

DEFAULT_CASES_PER_STRATUM = 4
DEFAULT_SEED_COUNT = 2
DEFAULT_JUDGE_WEIGHT = 0.2
DEFAULT_JUDGE_PACKET_MODE = "changed_unique"


def candidate_policy_payload() -> dict[str, Any]:
    return CANDIDATE_POLICY


# ---------------------------------------------------------------------------
# Fixed adapter section
# ---------------------------------------------------------------------------

def _candidate_policy_json() -> str:
    return json.dumps(candidate_policy_payload(), indent=2, sort_keys=True)


def resolve_default_judge_verdicts(explicit_path: Path | None = None) -> Path | None:
    if explicit_path is not None:
        return explicit_path
    env_path = os.environ.get(DEFAULT_JUDGE_VERDICTS_ENV)
    if not env_path:
        return None
    return Path(env_path).expanduser().resolve()


def _case_summary(candidate_case: dict[str, Any], incumbent_case: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": candidate_case["scenario_id"],
        "label": candidate_case["label"],
        "candidate_score": candidate_case["score"],
        "incumbent_score": incumbent_case["score"],
        "score_delta": round(candidate_case["score"] - incumbent_case["score"], 4),
        "candidate_top_ids": candidate_case["top_ids"],
        "incumbent_top_ids": incumbent_case["top_ids"],
        "candidate_failures": candidate_case["failures"],
        "incumbent_failures": incumbent_case["failures"],
    }


def _comparison_summary(candidate_report: dict[str, Any], incumbent_report: dict[str, Any]) -> dict[str, Any]:
    incumbent_cases = {
        case["scenario_id"]: case
        for case in incumbent_report["cases"]
    }
    changed_cases = []
    for candidate_case in candidate_report["cases"]:
        incumbent_case = incumbent_cases[candidate_case["scenario_id"]]
        changed = (
            candidate_case["score"] != incumbent_case["score"]
            or candidate_case["top_ids"] != incumbent_case["top_ids"]
            or candidate_case["failures"] != incumbent_case["failures"]
        )
        if changed:
            changed_cases.append(_case_summary(candidate_case, incumbent_case))

    return {
        "candidate_score": candidate_report["score"],
        "incumbent_score": incumbent_report["score"],
        "score_delta": round(candidate_report["score"] - incumbent_report["score"], 4),
        "candidate_total_failures": candidate_report["total_failures"],
        "incumbent_total_failures": incumbent_report["total_failures"],
        "candidate_total_checks": candidate_report["total_checks"],
        "incumbent_total_checks": incumbent_report["total_checks"],
        "changed_case_count": len(changed_cases),
        "changed_cases": changed_cases,
    }


def run_candidate_benchmark(
    *,
    cases_per_stratum: int = DEFAULT_CASES_PER_STRATUM,
    seed: int = 42,
    seed_count: int = DEFAULT_SEED_COUNT,
    judge_verdicts: Path | None = None,
    emit_judge_packets: Path | None = None,
    emit_judge_verdict_template: Path | None = None,
    judge_packet_mode: str = DEFAULT_JUDGE_PACKET_MODE,
) -> dict[str, Any]:
    scenario_tuple = build_public_frontier_benchmark_scenarios(
        cases_per_stratum=cases_per_stratum,
        seed=seed,
        seed_count=seed_count,
    )

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="public-policy-candidate-",
        delete=False,
    ) as tmp:
        tmp.write(_candidate_policy_json())
        candidate_path = Path(tmp.name)

    try:
        candidate_policy = load_public_policy_override(candidate_path)
    finally:
        candidate_path.unlink(missing_ok=True)

    candidate_report = run_public_frontier_benchmark(
        scenario_tuple,
        public_policy=candidate_policy,
    )
    incumbent_report = run_public_frontier_benchmark(scenario_tuple)

    candidate_report_dict = benchmark_report_to_dict(candidate_report, include_responses=False)
    incumbent_report_dict = benchmark_report_to_dict(incumbent_report, include_responses=False)

    summary = {
        "candidate_policy": candidate_policy_payload(),
        "scenarios": [scenario.id for scenario in scenario_tuple],
        "comparison": _comparison_summary(candidate_report_dict, incumbent_report_dict),
        "candidate_report": candidate_report_dict,
        "incumbent_report": incumbent_report_dict,
    }

    if emit_judge_packets is not None:
        packets = build_pairwise_judge_packets(
            candidate_report,
            incumbent_report,
            scenarios=scenario_tuple,
            mode=judge_packet_mode,
        )
        emit_judge_packets.write_text(
            json.dumps([judge_packet_to_dict(packet) for packet in packets], indent=2)
        )
        if emit_judge_verdict_template is not None:
            emit_judge_verdict_template.write_text(
                json.dumps(build_blank_judge_verdict_template(packets), indent=2)
            )
    elif emit_judge_verdict_template is not None:
        raise ValueError("emit_judge_verdict_template requires emit_judge_packets")

    if judge_verdicts is not None:
        verdicts = parse_public_frontier_judge_verdicts(
            json.loads(judge_verdicts.read_text())
        )
        judge_score = compute_pairwise_judge_score(verdicts)
        summary["judge_score"] = judge_score
        summary["hybrid_score"] = compute_hybrid_public_frontier_score(
            hard_score=candidate_report.score,
            judge_score=judge_score,
            judge_weight=DEFAULT_JUDGE_WEIGHT,
        )

    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary-json", action="store_true")
    parser.add_argument("--cases-per-stratum", type=int, default=DEFAULT_CASES_PER_STRATUM)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seed-count", type=int, default=DEFAULT_SEED_COUNT)
    parser.add_argument("--judge-verdicts", type=Path)
    parser.add_argument("--emit-judge-packets", type=Path)
    parser.add_argument("--emit-judge-verdict-template", type=Path)
    parser.add_argument(
        "--judge-packet-mode",
        choices=("all", "changed", "changed_unique"),
        default=DEFAULT_JUDGE_PACKET_MODE,
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if not args.summary_json and args.emit_judge_packets is None:
        raise SystemExit("Pass --summary-json and optionally --emit-judge-packets.")
    summary = run_candidate_benchmark(
        cases_per_stratum=args.cases_per_stratum,
        seed=args.seed,
        seed_count=args.seed_count,
        judge_verdicts=resolve_default_judge_verdicts(args.judge_verdicts),
        emit_judge_packets=args.emit_judge_packets,
        emit_judge_verdict_template=args.emit_judge_verdict_template,
        judge_packet_mode=args.judge_packet_mode,
    )
    if args.summary_json:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
