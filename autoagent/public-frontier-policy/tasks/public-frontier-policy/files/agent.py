#!/usr/bin/env python3
"""Task-local single-file public-policy harness for Harbor/AutoAgent benchmarks."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from optiqal import load_public_policy_override
from optiqal.public_frontier_benchmark import (
    CANONICAL_PUBLIC_FRONTIER_SCENARIOS,
    benchmark_report_to_dict,
    build_pairwise_judge_packets,
    compute_hybrid_public_frontier_score,
    compute_pairwise_judge_score,
    generate_stratified_public_frontier_scenarios,
    judge_packet_to_dict,
    parse_public_frontier_judge_verdicts,
    run_public_frontier_benchmark,
)


# ---------------------------------------------------------------------------
# Editable policy section
# ---------------------------------------------------------------------------

CANDIDATE_POLICY: dict[str, Any] = {
    "lanes": {},
    "conditions": {
        "cardiometabolic_signal": {
            "profile_score_threshold": 4,
        },
        "metabolic_signal": {
            "profile_score_threshold": 5,
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
DEFAULT_JUDGE_WEIGHT = 0.2


def candidate_policy_payload() -> dict[str, Any]:
    return CANDIDATE_POLICY


# ---------------------------------------------------------------------------
# Fixed adapter section
# ---------------------------------------------------------------------------

def _candidate_policy_json() -> str:
    return json.dumps(candidate_policy_payload(), indent=2, sort_keys=True)


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
    judge_verdicts: Path | None = None,
    emit_judge_packets: Path | None = None,
) -> dict[str, Any]:
    scenarios = list(CANONICAL_PUBLIC_FRONTIER_SCENARIOS)
    if cases_per_stratum > 0:
        scenarios.extend(
            generate_stratified_public_frontier_scenarios(
                seed=seed,
                cases_per_stratum=cases_per_stratum,
            )
        )
    scenario_tuple = tuple(scenarios)

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
        )
        emit_judge_packets.write_text(
            json.dumps([judge_packet_to_dict(packet) for packet in packets], indent=2)
        )

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
    parser.add_argument("--judge-verdicts", type=Path)
    parser.add_argument("--emit-judge-packets", type=Path)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if not args.summary_json and args.emit_judge_packets is None:
        raise SystemExit("Pass --summary-json and optionally --emit-judge-packets.")
    summary = run_candidate_benchmark(
        cases_per_stratum=args.cases_per_stratum,
        seed=args.seed,
        judge_verdicts=args.judge_verdicts,
        emit_judge_packets=args.emit_judge_packets,
    )
    if args.summary_json:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
