"""Smoke tests for the public-frontier AutoAgent sidecar harness."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "autoagent" / "public-frontier-policy" / "agent.py"


def test_autoagent_public_frontier_harness_emits_summary_json():
    result = subprocess.run(
        [sys.executable, str(HARNESS), "--summary-json"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert "comparison" in payload
    assert payload["comparison"]["candidate_score"] <= 1.0
    assert "healthy_35f_public" in payload["scenarios"]
