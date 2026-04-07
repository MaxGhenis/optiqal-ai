"""Compare a candidate public-policy override against the incumbent public frontier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from optiqal import load_public_policy_override
from optiqal.public_frontier_benchmark import (
    benchmark_report_to_dict,
    build_public_frontier_benchmark_scenarios,
    build_pairwise_judge_packets,
    compute_hybrid_public_frontier_score,
    compute_pairwise_judge_score,
    judge_packet_to_dict,
    parse_public_frontier_judge_verdicts,
    run_public_frontier_benchmark,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-policy",
        type=Path,
        required=True,
        help="Candidate public-policy override JSON.",
    )
    parser.add_argument(
        "--incumbent-policy",
        type=Path,
        help="Optional incumbent public-policy override JSON. Defaults to the live built-in policy.",
    )
    parser.add_argument(
        "--cases-per-stratum",
        type=int,
        default=0,
        help="Append generated stratified scenarios beyond the canonical canaries.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for generated stratified scenarios.",
    )
    parser.add_argument(
        "--seed-count",
        type=int,
        default=1,
        help="Number of consecutive generation seeds to evaluate starting at --seed.",
    )
    parser.add_argument(
        "--emit-judge-packets",
        type=Path,
        help="Write pairwise judge packets JSON comparing candidate A vs incumbent B.",
    )
    parser.add_argument(
        "--judge-verdicts",
        type=Path,
        help="Load offline judge verdict JSON and compute judge/hybrid score for candidate A.",
    )
    parser.add_argument(
        "--judge-weight",
        type=float,
        default=0.2,
        help="Weight for the judge score once hard rules pass.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write the comparison summary JSON to this path.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the comparison summary as JSON.",
    )
    return parser


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


def main() -> None:
    args = _build_parser().parse_args()

    scenario_tuple = build_public_frontier_benchmark_scenarios(
        cases_per_stratum=args.cases_per_stratum,
        seed=args.seed,
        seed_count=args.seed_count,
    )

    candidate_policy = load_public_policy_override(args.candidate_policy)
    incumbent_policy = (
        load_public_policy_override(args.incumbent_policy)
        if args.incumbent_policy is not None
        else None
    )

    candidate_report = run_public_frontier_benchmark(
        scenario_tuple,
        public_policy=candidate_policy,
    )
    incumbent_report = run_public_frontier_benchmark(
        scenario_tuple,
        public_policy=incumbent_policy,
    )
    candidate_report_dict = benchmark_report_to_dict(candidate_report, include_responses=False)
    incumbent_report_dict = benchmark_report_to_dict(incumbent_report, include_responses=False)

    summary = {
        "candidate_policy_path": str(args.candidate_policy),
        "incumbent_policy_path": (
            str(args.incumbent_policy) if args.incumbent_policy is not None else None
        ),
        "scenarios": [scenario.id for scenario in scenario_tuple],
        "comparison": _comparison_summary(candidate_report_dict, incumbent_report_dict),
        "candidate_report": candidate_report_dict,
        "incumbent_report": incumbent_report_dict,
    }

    if args.emit_judge_packets is not None:
        packets = build_pairwise_judge_packets(
            candidate_report,
            incumbent_report,
            scenarios=scenario_tuple,
        )
        args.emit_judge_packets.write_text(
            json.dumps([judge_packet_to_dict(packet) for packet in packets], indent=2)
        )

    if args.judge_verdicts is not None:
        verdicts = parse_public_frontier_judge_verdicts(
            json.loads(args.judge_verdicts.read_text())
        )
        judge_score = compute_pairwise_judge_score(verdicts)
        summary["judge_score"] = judge_score
        summary["hybrid_score"] = compute_hybrid_public_frontier_score(
            hard_score=candidate_report.score,
            judge_score=judge_score,
            judge_weight=args.judge_weight,
        )

    if args.output is not None:
        args.output.write_text(json.dumps(summary, indent=2))

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    comparison = summary["comparison"]
    print(
        "Candidate vs incumbent public frontier: "
        f"{comparison['candidate_score']:.3f} vs {comparison['incumbent_score']:.3f} "
        f"(delta {comparison['score_delta']:+.3f})"
    )
    print(
        f"Failures: {comparison['candidate_total_failures']} candidate, "
        f"{comparison['incumbent_total_failures']} incumbent"
    )
    for case in comparison["changed_cases"]:
        print(
            f"- {case['scenario_id']}: {case['candidate_score']:.3f} vs "
            f"{case['incumbent_score']:.3f}"
        )
        if case["candidate_top_ids"] != case["incumbent_top_ids"]:
            print(f"  candidate top ids: {case['candidate_top_ids']}")
            print(f"  incumbent top ids: {case['incumbent_top_ids']}")
        for failure in case["candidate_failures"]:
            print(f"  candidate fail {failure['rule']}: {failure['message']}")
        for failure in case["incumbent_failures"]:
            print(f"  incumbent fail {failure['rule']}: {failure['message']}")
    if args.judge_verdicts is not None:
        print(f"Judge score (candidate A preference): {summary['judge_score']:.3f}")
        print(f"Hybrid score: {summary['hybrid_score']:.3f}")


if __name__ == "__main__":
    main()
