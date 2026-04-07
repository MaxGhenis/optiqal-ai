#!/usr/bin/env python3
"""Export the Optiqal public-frontier sidecar into an AutoAgent workspace layout."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


SIDECAR_ROOT = Path(__file__).resolve().parent
TASK_ROOT = SIDECAR_ROOT / "tasks" / "public-frontier-policy"

ROOT_COPY_MAP = {
    SIDECAR_ROOT / "agent.py": Path("agent.py"),
    SIDECAR_ROOT / "program.md": Path("program.md"),
}

TASK_COPY_MAP = {
    TASK_ROOT / "instruction.md": Path("tasks") / "public-frontier-policy" / "instruction.md",
    TASK_ROOT / "task.toml": Path("tasks") / "public-frontier-policy" / "task.toml",
    TASK_ROOT / "environment" / "Dockerfile": (
        Path("tasks") / "public-frontier-policy" / "environment" / "Dockerfile"
    ),
    TASK_ROOT / "files" / "agent.py": (
        Path("tasks") / "public-frontier-policy" / "files" / "agent.py"
    ),
    TASK_ROOT / "files" / "program.md": (
        Path("tasks") / "public-frontier-policy" / "files" / "program.md"
    ),
    TASK_ROOT / "tests" / "test.sh": (
        Path("tasks") / "public-frontier-policy" / "tests" / "test.sh"
    ),
    TASK_ROOT / "tests" / "score_task.py": (
        Path("tasks") / "public-frontier-policy" / "tests" / "score_task.py"
    ),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="AutoAgent workspace root to populate.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files in the target workspace.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned writes without modifying the target workspace.",
    )
    parser.add_argument(
        "--include-root",
        action="store_true",
        help="Also export root agent.py/program.md even if the target already has them.",
    )
    return parser


def _copy_file(source: Path, destination: Path, *, force: bool, dry_run: bool) -> None:
    if destination.exists() and not force:
        raise FileExistsError(
            f"Refusing to overwrite existing file without --force: {destination}"
        )
    if dry_run:
        print(f"{source} -> {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _should_copy_root(target: Path, *, include_root: bool) -> bool:
    if include_root:
        return True
    return not ((target / "agent.py").exists() or (target / "program.md").exists())


def bootstrap_workspace(
    target: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
    include_root: bool = False,
) -> None:
    copy_map = dict(TASK_COPY_MAP)
    if _should_copy_root(target, include_root=include_root):
        copy_map = {**ROOT_COPY_MAP, **copy_map}
    elif dry_run:
        print("Skipping root agent.py/program.md because target already has them.")

    for source, relative_destination in copy_map.items():
        _copy_file(
            source,
            target / relative_destination,
            force=force,
            dry_run=dry_run,
        )


def main() -> None:
    args = _build_parser().parse_args()
    bootstrap_workspace(
        args.target,
        force=args.force,
        dry_run=args.dry_run,
        include_root=args.include_root,
    )


if __name__ == "__main__":
    main()
