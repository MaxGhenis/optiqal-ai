"""Smoke tests for exporting the public-frontier sidecar into an AutoAgent workspace."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "autoagent" / "public-frontier-policy" / "bootstrap_autoagent_workspace.py"


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
