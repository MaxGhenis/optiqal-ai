"""Smoke tests for exporting the public-frontier sidecar into an AutoAgent workspace."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "autoagent" / "public-frontier-policy" / "bootstrap_autoagent_workspace.py"
PREFLIGHT = ROOT / "autoagent" / "public-frontier-policy" / "check_autoagent_workspace.py"


def test_autoagent_workspace_bootstrap_exports_expected_files(tmp_path: Path) -> None:
    workspace = tmp_path / "autoagent-workspace"
    subprocess.run(
        [
            sys.executable,
            str(BOOTSTRAP),
            "--target",
            str(workspace),
        ],
        cwd=ROOT,
        check=True,
    )

    assert (workspace / "agent.py").exists()
    assert (workspace / "program.md").exists()
    assert (
        workspace
        / "tasks"
        / "public-frontier-policy"
        / "task.toml"
    ).exists()
    assert (
        workspace
        / "tasks"
        / "public-frontier-policy"
        / "files"
        / "agent.py"
    ).exists()

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "python")
    result = subprocess.run(
        [
            sys.executable,
            str(workspace / "agent.py"),
            "--summary-json",
        ],
        cwd=workspace,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert "comparison" in payload


def test_bootstrap_does_not_overwrite_existing_root_harness_by_default(tmp_path: Path) -> None:
    workspace = tmp_path / "autoagent-workspace"
    workspace.mkdir()
    (workspace / "agent.py").write_text("class AutoAgent:\n    pass\n")
    (workspace / "program.md").write_text("upstream program\n")

    subprocess.run(
        [
            sys.executable,
            str(BOOTSTRAP),
            "--target",
            str(workspace),
        ],
        cwd=ROOT,
        check=True,
    )

    assert (workspace / "agent.py").read_text() == "class AutoAgent:\n    pass\n"
    assert (workspace / "program.md").read_text() == "upstream program\n"
    assert (
        workspace / "tasks" / "public-frontier-policy" / "task.toml"
    ).exists()


def test_preflight_fails_without_provider_env(tmp_path: Path) -> None:
    workspace = tmp_path / "autoagent-workspace"
    workspace.mkdir()
    (workspace / "agent.py").write_text(
        "from agents import Runner\nMODEL = \"gpt-5\"\nclass AutoAgent:\n    pass\n"
    )
    task_dir = workspace / "tasks" / "public-frontier-policy"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text("name = 'public-frontier-policy'\n")

    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("ANTHROPIC_API_KEY", None)
    env["PATH"] = os.environ["PATH"]

    result = subprocess.run(
        [
            sys.executable,
            str(PREFLIGHT),
            "--workspace",
            str(workspace),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "OPENAI_API_KEY or ANTHROPIC_API_KEY is set" in result.stdout
