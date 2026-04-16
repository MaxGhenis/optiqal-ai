#!/usr/bin/env python3
"""Compatibility wrapper for the packaged Pan-UKB download workflow."""

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

    if not args or args == ["--help"]:
        return pan_ukb_main(["describe", "--data-dir", str(repo_data_dir)])
    if args == ["--download"]:
        return pan_ukb_main(["download", "--data-dir", str(repo_data_dir)])
    if args == ["--generate-wget-script"]:
        return pan_ukb_main(
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
