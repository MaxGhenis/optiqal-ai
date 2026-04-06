"""Run the public-frontier benchmark harness."""

from __future__ import annotations

import argparse
import json

from optiqal.public_frontier_benchmark import (
    CANONICAL_PUBLIC_FRONTIER_SCENARIOS,
    generate_stratified_public_frontier_scenarios,
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
    return parser


def _report_dict(report) -> dict:
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
                "top_ids": list(result.top_ids),
                "failures": [
                    {"rule": failure.rule, "message": failure.message}
                    for failure in result.failures
                ],
            }
            for result in report.case_results
        ],
    }


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

    if args.json:
        print(json.dumps(_report_dict(report), indent=2))
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


if __name__ == "__main__":
    main()
