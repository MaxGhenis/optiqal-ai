#!/usr/bin/env python3
"""Compatibility wrapper for the packaged Pan-UKB download workflow."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))


def _run_pan_ukb(argv: list[str]) -> int:
    module_path = PYTHON_ROOT / "optiqal" / "validation" / "pan_ukb.py"
    module_name = "pan_ukb_wrapper_module"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load Pan-UKB module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module.main(argv)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    repo_data_dir = REPO_ROOT / "data" / "pan-ukb"

    if not args or args == ["--help"]:
        return _run_pan_ukb(["describe", "--data-dir", str(repo_data_dir)])
    if args == ["--download"]:
        return _run_pan_ukb(["download", "--data-dir", str(repo_data_dir)])
    if args == ["--generate-wget-script"]:
        return _run_pan_ukb(
            ["generate-wget-script", "--data-dir", str(repo_data_dir)]
        )

    print(
        "Usage: python scripts/download-pan-ukb.py "
        "[--download|--generate-wget-script|--help]",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
