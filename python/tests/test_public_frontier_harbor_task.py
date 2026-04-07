"""Smoke tests for the Harbor-style public-frontier policy task bundle."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ROOT_AGENT = ROOT / "autoagent" / "public-frontier-policy" / "agent.py"
TASK_DOCKERFILE = (
    ROOT
    / "autoagent"
    / "public-frontier-policy"
    / "tasks"
    / "public-frontier-policy"
    / "environment"
    / "Dockerfile"
)
TASK_TEST_SH = (
    ROOT
    / "autoagent"
    / "public-frontier-policy"
    / "tasks"
    / "public-frontier-policy"
    / "tests"
    / "test.sh"
)


def test_harbor_task_dockerfile_does_not_copy_task_files_from_wrong_context() -> None:
    dockerfile = TASK_DOCKERFILE.read_text()

    assert "COPY files/" not in dockerfile
    assert "chmod +x /app/agent.py" not in dockerfile


def test_harbor_task_verifier_does_not_expect_agent_file_in_container() -> None:
    test_sh = TASK_TEST_SH.read_text()

    assert "/app/agent.py" not in test_sh
    assert "reward.json" in test_sh
    assert "reward.txt" in test_sh


def test_public_policy_root_agent_emits_summary_json() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "python")

    result = subprocess.run(
        [sys.executable, str(ROOT_AGENT), "--summary-json"],
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


def test_public_policy_root_agent_exports_autoagent_class() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "python")

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util, pathlib; "
                f"path = pathlib.Path({str(ROOT_AGENT)!r}); "
                "spec = importlib.util.spec_from_file_location('public_policy_agent', path); "
                "mod = importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(mod); "
                "print(hasattr(mod, 'AutoAgent'))"
            ),
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "True"
