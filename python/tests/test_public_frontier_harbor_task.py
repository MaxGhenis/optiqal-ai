"""Smoke tests for the Harbor-style public-frontier policy task bundle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TASK_AGENT = (
    ROOT
    / "autoagent"
    / "public-frontier-policy"
    / "tasks"
    / "public-frontier-policy"
    / "files"
    / "agent.py"
)
TASK_DOCKERFILE = (
    ROOT
    / "autoagent"
    / "public-frontier-policy"
    / "tasks"
    / "public-frontier-policy"
    / "environment"
    / "Dockerfile"
)


def test_harbor_task_dockerfile_does_not_copy_task_files_from_wrong_context() -> None:
    dockerfile = TASK_DOCKERFILE.read_text()

    assert "COPY files/" not in dockerfile
    assert "chmod +x /app/agent.py" not in dockerfile


def test_harbor_task_agent_emits_summary_json() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "python")

    result = subprocess.run(
        [sys.executable, str(TASK_AGENT), "--summary-json"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert "comparison" in payload
    assert payload["comparison"]["candidate_score"] <= 1.0
    assert "healthy_35f_public" in payload["scenarios"]
