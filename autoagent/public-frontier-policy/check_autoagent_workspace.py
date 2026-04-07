#!/usr/bin/env python3
"""Fail-fast checks before running the Optiqal AutoAgent task in a workspace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
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


def _missing_docker_credential_helpers() -> list[str]:
    config_dir = Path(os.environ.get("DOCKER_CONFIG", Path.home() / ".docker"))
    config_path = config_dir / "config.json"
    if not config_path.exists():
        return []

    try:
        config = json.loads(config_path.read_text())
    except json.JSONDecodeError:
        return []

    helpers: set[str] = set()
    creds_store = config.get("credsStore")
    if isinstance(creds_store, str) and creds_store:
        helpers.add(creds_store)

    cred_helpers = config.get("credHelpers")
    if isinstance(cred_helpers, dict):
        helpers.update(
            helper
            for helper in cred_helpers.values()
            if isinstance(helper, str) and helper
        )

    missing = []
    for helper in sorted(helpers):
        executable = f"docker-credential-{helper}"
        if shutil.which(executable) is None:
            missing.append(executable)
    return missing


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

    missing_helpers = _missing_docker_credential_helpers()
    helper_guidance = (
        "Add the Docker helper directory to PATH, e.g. "
        "export PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH"
    )
    _check(
        not missing_helpers,
        "Docker credential helper(s) are on PATH"
        if not missing_helpers
        else f"Missing Docker credential helper(s): {', '.join(missing_helpers)}. "
        f"{helper_guidance}",
    )

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
