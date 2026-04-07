#!/usr/bin/env python3
"""Single-file public-policy harness for AutoAgent-style optimization."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


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
    finally:
        candidate_path.unlink(missing_ok=True)


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


if __name__ == "__main__":
    main()
