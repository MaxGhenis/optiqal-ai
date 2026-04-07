#!/usr/bin/env python3
"""Fail-fast checks before running the Optiqal AutoAgent task in a workspace."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace",
        type=Path,
        required=True,
        help="AutoAgent workspace root to validate.",
    )
    return parser


def _check(condition: bool, message: str) -> None:
    prefix = "OK" if condition else "FAIL"
    print(f"[{prefix}] {message}")
    if not condition:
        raise SystemExit(1)


def _file_contains(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text()


def _requires_provider_env(agent_path: Path) -> bool:
    if not agent_path.exists():
        return False
    text = agent_path.read_text()
    return (
        "from agents import" in text
        or "Runner.run(" in text
        or 'MODEL = "gpt' in text
        or 'MODEL = "claude' in text
    )


def main() -> None:
    args = _build_parser().parse_args()
    workspace = args.workspace.resolve()
    agent_path = workspace / "agent.py"

    _check(workspace.exists(), f"workspace exists: {workspace}")
    _check(agent_path.exists(), "workspace root agent.py exists")
    _check(
        _file_contains(agent_path, "class AutoAgent"),
        "workspace root agent.py still contains AutoAgent",
    )
    _check(
        (workspace / "tasks" / "public-frontier-policy" / "task.toml").exists(),
        "public-frontier-policy task bundle exists",
    )
    if _requires_provider_env(agent_path):
        _check(
            any(os.environ.get(key) for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")),
            "OPENAI_API_KEY or ANTHROPIC_API_KEY is set",
        )
    else:
        _check(True, "root harness does not require provider credentials")

    docker = subprocess.run(
        ["docker", "info"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    _check(docker.returncode == 0, "Docker daemon is reachable")

    uv = subprocess.run(
        ["uv", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    _check(uv.returncode == 0, "uv is installed")

    print("Workspace preflight passed.")


if __name__ == "__main__":
    main()
