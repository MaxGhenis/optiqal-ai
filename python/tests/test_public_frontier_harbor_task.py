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
SCORE_TASK = (
    ROOT
    / "autoagent"
    / "public-frontier-policy"
    / "tasks"
    / "public-frontier-policy"
    / "tests"
    / "score_task.py"
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


def test_public_policy_root_agent_emits_focused_judge_packets_and_template(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "python")
    packets_path = tmp_path / "judge-packets.json"
    verdict_template_path = tmp_path / "judge-verdicts.template.json"

    subprocess.run(
        [
            sys.executable,
            str(ROOT_AGENT),
            "--summary-json",
            "--emit-judge-packets",
            str(packets_path),
            "--emit-judge-verdict-template",
            str(verdict_template_path),
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    packets = json.loads(packets_path.read_text())
    verdict_template = json.loads(verdict_template_path.read_text())
    assert packets
    assert len(verdict_template) == len(packets)
    assert len(packets) < 10
    assert verdict_template[0]["winner"] == "A|B|tie"


def test_harbor_score_task_prefers_hybrid_score_when_present(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.json"
    logs_dir = tmp_path / "logs"
    summary_path.write_text(json.dumps({
        "comparison": {
            "candidate_score": 1.0,
            "incumbent_score": 0.95,
            "score_delta": 0.05,
            "changed_case_count": 3,
        },
        "judge_score": 0.4,
        "hybrid_score": 0.88,
    }))

    env = dict(os.environ)
    env["HARBOR_VERIFIER_LOG_DIR"] = str(logs_dir)
    subprocess.run(
        [sys.executable, str(SCORE_TASK), str(summary_path)],
        cwd=ROOT,
        env=env,
        check=True,
    )

    reward_payload = json.loads((logs_dir / "reward.json").read_text())
    assert reward_payload["candidate_score"] == 0.88
    assert reward_payload["hard_candidate_score"] == 1.0
    assert reward_payload["score_mode"] == "hybrid"
