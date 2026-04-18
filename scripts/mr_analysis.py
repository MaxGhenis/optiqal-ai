#!/usr/bin/env python3
"""Compatibility wrapper for the packaged Pan-UKB MR analysis workflow."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = REPO_ROOT / "python"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from optiqal.validation.pan_ukb import main as pan_ukb_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    repo_data_dir = REPO_ROOT / "data" / "pan-ukb"
    return pan_ukb_main(["analyze", "--data-dir", str(repo_data_dir), *args])


if __name__ == "__main__":
    raise SystemExit(main())
