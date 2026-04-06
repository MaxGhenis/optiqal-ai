"""Run the public-frontier benchmark harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from optiqal.public_frontier_benchmark import (
    CANONICAL_PUBLIC_FRONTIER_SCENARIOS,
    benchmark_report_from_dict,
    benchmark_report_to_dict,
    build_pairwise_judge_packets,
    compute_hybrid_public_frontier_score,
    compute_pairwise_judge_score,
    generate_stratified_public_frontier_scenarios,
    judge_packet_to_dict,
    parse_public_frontier_judge_verdicts,
    run_public_frontier_benchmark,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
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
        "--json",
        action="store_true",
        help="Emit the benchmark report as JSON.",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        help="Write the full benchmark report JSON to this path.",
    )
    parser.add_argument(
        "--judge-against-report",
        type=Path,
        help="Load another benchmark report JSON and emit pairwise judge packets versus it.",
    )
    parser.add_argument(
        "--emit-judge-packets",
        type=Path,
        help="Write pairwise judge packets JSON to this path.",
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
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    scenarios = list(CANONICAL_PUBLIC_FRONTIER_SCENARIOS)
    if args.cases_per_stratum > 0:
        scenarios.extend(
            generate_stratified_public_frontier_scenarios(
                seed=args.seed,
                cases_per_stratum=args.cases_per_stratum,
            )
        )

    report = run_public_frontier_benchmark(tuple(scenarios))
    report_dict = benchmark_report_to_dict(report, include_responses=True)

    if args.output_report is not None:
        args.output_report.write_text(json.dumps(report_dict, indent=2))

    if args.emit_judge_packets is not None:
        if args.judge_against_report is None:
            raise SystemExit("--emit-judge-packets requires --judge-against-report")
        other_report = benchmark_report_from_dict(
            json.loads(args.judge_against_report.read_text())
        )
        packets = build_pairwise_judge_packets(report, other_report, scenarios=tuple(scenarios))
        args.emit_judge_packets.write_text(
            json.dumps([judge_packet_to_dict(packet) for packet in packets], indent=2)
        )

    if args.json:
        output = dict(report_dict)
        if args.judge_verdicts is not None:
            verdicts = parse_public_frontier_judge_verdicts(
                json.loads(args.judge_verdicts.read_text())
            )
            judge_score = compute_pairwise_judge_score(verdicts)
            output["judge_score"] = judge_score
            output["hybrid_score"] = compute_hybrid_public_frontier_score(
                hard_score=report.score,
                judge_score=judge_score,
                judge_weight=args.judge_weight,
            )
        print(json.dumps(output, indent=2))
        return

    print(f"Public frontier benchmark score: {report.score:.3f}")
    print(f"Checks: {report.total_checks} total, {report.total_failures} failed")
    for result in report.case_results:
        status = "PASS" if result.passed else "FAIL"
        print(
            f"- {status} {result.scenario_id}: "
            f"{result.checks_run - result.checks_failed}/{result.checks_run} checks"
        )
        for failure in result.failures:
            print(f"  - {failure.rule}: {failure.message}")

    if args.judge_verdicts is not None:
        verdicts = parse_public_frontier_judge_verdicts(
            json.loads(args.judge_verdicts.read_text())
        )
        judge_score = compute_pairwise_judge_score(verdicts)
        hybrid_score = compute_hybrid_public_frontier_score(
            hard_score=report.score,
            judge_score=judge_score,
            judge_weight=args.judge_weight,
        )
        print(f"Judge score (candidate A preference): {judge_score:.3f}")
        print(f"Hybrid score: {hybrid_score:.3f}")


if __name__ == "__main__":
    main()
