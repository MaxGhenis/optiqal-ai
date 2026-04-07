#!/usr/bin/env python3
"""Single-file Harbor-compatible public-policy harness for AutoAgent optimization."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from harbor.agents.base import BaseAgent
    from harbor.environments.base import BaseEnvironment
    from harbor.models.agent.context import AgentContext
except ModuleNotFoundError:  # pragma: no cover - local CLI path may not have harbor installed.
    BaseAgent = object  # type: ignore[assignment]
    BaseEnvironment = Any  # type: ignore[assignment]
    AgentContext = Any  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "python" / "scripts" / "run_public_frontier_candidate.py"
PYTHON = ROOT / "python" / ".venv" / "bin" / "python"


# ---------------------------------------------------------------------------
# Editable policy section
# ---------------------------------------------------------------------------

# Keep this object small and explicit. The optimizer should change policy data,
# not rework the benchmark runner or the core model.
CANDIDATE_POLICY: dict[str, Any] = {
    "lanes": {},
    "conditions": {
        "cardiometabolic_signal": {
            "profile_score_threshold": 4,
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

DEFAULT_CASES_PER_STRATUM = 2
DEFAULT_JUDGE_WEIGHT = 0.2


def candidate_policy_payload() -> dict[str, Any]:
    """Return the current candidate policy payload."""
    return CANDIDATE_POLICY


# ---------------------------------------------------------------------------
# Fixed adapter section
# ---------------------------------------------------------------------------

def _candidate_policy_json() -> str:
    return json.dumps(candidate_policy_payload(), indent=2, sort_keys=True)


def write_candidate_policy(path: Path) -> None:
    path.write_text(_candidate_policy_json())


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


def _run_candidate_benchmark_in_process(
    *,
    candidate_path: Path,
    cases_per_stratum: int,
    seed: int,
    judge_verdicts: Path | None,
    emit_judge_packets: Path | None,
) -> dict[str, Any]:
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

    scenarios = list(CANONICAL_PUBLIC_FRONTIER_SCENARIOS)
    if cases_per_stratum > 0:
        scenarios.extend(
            generate_stratified_public_frontier_scenarios(
                seed=seed,
                cases_per_stratum=cases_per_stratum,
            )
        )
    scenario_tuple = tuple(scenarios)

    candidate_policy = load_public_policy_override(candidate_path)
    candidate_report = run_public_frontier_benchmark(
        scenario_tuple,
        public_policy=candidate_policy,
    )
    incumbent_report = run_public_frontier_benchmark(scenario_tuple)

    candidate_report_dict = benchmark_report_to_dict(candidate_report, include_responses=False)
    incumbent_report_dict = benchmark_report_to_dict(incumbent_report, include_responses=False)
    summary = {
        "candidate_policy_path": str(candidate_path),
        "incumbent_policy_path": None,
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


def run_candidate_benchmark(
    *,
    cases_per_stratum: int = DEFAULT_CASES_PER_STRATUM,
    seed: int = 42,
    judge_verdicts: Path | None = None,
    emit_judge_packets: Path | None = None,
    output: Path | None = None,
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        prefix="public-policy-candidate-",
        delete=False,
    ) as tmp:
        tmp.write(_candidate_policy_json())
        candidate_path = Path(tmp.name)

    try:
        if RUNNER.exists() and PYTHON.exists():
            command = [
                str(PYTHON),
                str(RUNNER),
                "--candidate-policy",
                str(candidate_path),
                "--cases-per-stratum",
                str(cases_per_stratum),
                "--seed",
                str(seed),
                "--json",
            ]
            if judge_verdicts is not None:
                command.extend(
                    [
                        "--judge-verdicts",
                        str(judge_verdicts),
                        "--judge-weight",
                        str(DEFAULT_JUDGE_WEIGHT),
                    ]
                )
            if emit_judge_packets is not None:
                command.extend(["--emit-judge-packets", str(emit_judge_packets)])
            if output is not None:
                command.extend(["--output", str(output)])

            result = subprocess.run(
                command,
                cwd=str(ROOT / "python"),
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(result.stdout)

        summary = _run_candidate_benchmark_in_process(
            candidate_path=candidate_path,
            cases_per_stratum=cases_per_stratum,
            seed=seed,
            judge_verdicts=judge_verdicts,
            emit_judge_packets=emit_judge_packets,
        )
        if output is not None:
            output.write_text(json.dumps(summary, indent=2))
        return summary
    finally:
        candidate_path.unlink(missing_ok=True)


def compute_reward(summary: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    comparison = summary["comparison"]
    candidate_score = float(comparison["candidate_score"])
    incumbent_score = float(comparison["incumbent_score"])
    reward = max(0.0, min(1.0, candidate_score + max(0.0, candidate_score - incumbent_score)))
    diagnostics = {
        "candidate_score": candidate_score,
        "incumbent_score": incumbent_score,
        "score_delta": float(comparison["score_delta"]),
        "changed_case_count": int(comparison["changed_case_count"]),
        "reward": reward,
    }
    return reward, diagnostics


def _atif_trajectory(summary: dict[str, Any], duration_ms: int) -> dict[str, Any]:
    comparison = summary["comparison"]
    now = datetime.now(timezone.utc).isoformat()
    changed_cases = comparison["changed_cases"][:5]
    changed_summary = (
        "\n".join(
            f"- {case['scenario_id']}: {case['score_delta']:+.3f} "
            f"{case['candidate_top_ids']} vs {case['incumbent_top_ids']}"
            for case in changed_cases
        )
        if changed_cases
        else "No changed cases."
    )
    return {
        "schema_version": "ATIF-v1.6",
        "session_id": f"public-policy-{int(time.time() * 1000)}",
        "agent": {"name": "autoagent", "version": "0.1.0", "model_name": "static-policy"},
        "steps": [
            {
                "step_id": 1,
                "timestamp": now,
                "source": "agent",
                "message": (
                    "Evaluated the current candidate public policy against the incumbent.\n"
                    f"Candidate score: {comparison['candidate_score']:.3f}\n"
                    f"Incumbent score: {comparison['incumbent_score']:.3f}\n"
                    f"Score delta: {comparison['score_delta']:+.3f}\n"
                    f"Changed cases:\n{changed_summary}"
                ),
                "model_name": "static-policy",
            }
        ],
        "final_metrics": {
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_cached_tokens": 0,
            "total_cost_usd": 0,
            "total_steps": 1,
            "extra": {"duration_ms": duration_ms, "num_turns": 1},
        },
    }


class AutoAgent(BaseAgent):
    """Harbor adapter that benchmarks the embedded candidate policy directly."""

    SUPPORTS_ATIF = True

    @staticmethod
    def name() -> str:
        return "autoagent"

    def version(self) -> str | None:
        return "0.1.0"

    async def setup(self, environment: BaseEnvironment) -> None:
        await environment.exec(command="mkdir -p /logs/verifier /task")

    async def run(self, instruction: str, environment: BaseEnvironment, context: AgentContext) -> None:
        t0 = time.time()
        summary = run_candidate_benchmark()
        duration_ms = int((time.time() - t0) * 1000)
        reward, diagnostics = compute_reward(summary)

        verifier_dir = self.logs_dir / "verifier"
        verifier_dir.mkdir(parents=True, exist_ok=True)
        summary_path = verifier_dir / "summary.json"
        reward_json_path = verifier_dir / "reward.json"
        reward_txt_path = verifier_dir / "reward.txt"
        policy_path = self.logs_dir / "candidate_policy.json"
        trajectory_path = self.logs_dir / "trajectory.json"

        summary_path.write_text(json.dumps(summary, indent=2))
        reward_json_path.write_text(json.dumps(diagnostics, indent=2))
        reward_txt_path.write_text(f"{reward}\n")
        policy_path.write_text(_candidate_policy_json())
        trajectory_path.write_text(json.dumps(_atif_trajectory(summary, duration_ms), indent=2))

        await environment.exec(command="mkdir -p /logs/verifier /task")
        await environment.upload_file(source_path=summary_path, target_path="/logs/verifier/summary.json")
        await environment.upload_file(source_path=reward_json_path, target_path="/logs/verifier/reward.json")
        await environment.upload_file(source_path=reward_txt_path, target_path="/logs/verifier/reward.txt")
        await environment.upload_file(source_path=policy_path, target_path="/task/candidate_policy.json")

        comparison = summary["comparison"]
        context.cost_usd = 0
        context.n_input_tokens = 0
        context.n_output_tokens = 0
        context.n_cache_tokens = 0
        print(
            "policy benchmark "
            f"candidate={comparison['candidate_score']:.3f} "
            f"incumbent={comparison['incumbent_score']:.3f} "
            f"reward={reward:.3f} duration_ms={duration_ms}"
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--emit-policy",
        type=Path,
        help="Write the current candidate policy JSON to this path.",
    )
    parser.add_argument(
        "--summary-json",
        action="store_true",
        help="Print the candidate-vs-incumbent comparison JSON.",
    )
    parser.add_argument(
        "--cases-per-stratum",
        type=int,
        default=DEFAULT_CASES_PER_STRATUM,
        help="Append generated stratified scenarios beyond the canonical canaries.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for generated stratified scenarios.",
    )
    parser.add_argument(
        "--judge-verdicts",
        type=Path,
        help="Optional offline judge verdict JSON for hybrid scoring.",
    )
    parser.add_argument(
        "--emit-judge-packets",
        type=Path,
        help="Optional path to write pairwise judge packets.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the comparison JSON.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if args.emit_policy is not None:
        write_candidate_policy(args.emit_policy)

    if args.summary_json or args.output is not None or args.emit_judge_packets is not None:
        summary = run_candidate_benchmark(
            cases_per_stratum=args.cases_per_stratum,
            seed=args.seed,
            judge_verdicts=args.judge_verdicts,
            emit_judge_packets=args.emit_judge_packets,
            output=args.output,
        )
        if args.summary_json:
            print(json.dumps(summary, indent=2))
        return

    parser = _build_parser()
    parser.print_help(sys.stderr)
    raise SystemExit(1)


__all__ = ["AutoAgent"]


if __name__ == "__main__":
    main()
