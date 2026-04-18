#!/usr/bin/env python3
"""Score the public-policy task from the agent summary JSON."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main() -> None:
    summary_path = Path(sys.argv[1])
    summary = json.loads(summary_path.read_text())
    comparison = summary["comparison"]
    candidate_score = float(summary.get("hybrid_score", comparison["candidate_score"]))
    incumbent_score = float(comparison["incumbent_score"])

    reward = max(0.0, min(1.0, candidate_score))

    diagnostics = {
        "candidate_score": candidate_score,
        "hard_candidate_score": float(comparison["candidate_score"]),
        "incumbent_score": incumbent_score,
        "score_delta": float(comparison["score_delta"]),
        "changed_case_count": int(comparison["changed_case_count"]),
        "judge_score": summary.get("judge_score"),
        "score_mode": "hybrid" if "hybrid_score" in summary else "hard",
        "reward": reward,
    }
    logs_dir = Path(os.getenv("HARBOR_VERIFIER_LOG_DIR", "/logs/verifier"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    (logs_dir / "reward.json").write_text(json.dumps(diagnostics, indent=2))
    (logs_dir / "reward.txt").write_text(f"{reward}\n")


if __name__ == "__main__":
    main()
