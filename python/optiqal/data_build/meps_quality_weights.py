"""Build runtime quality weights from the committed MEPS calibration.

Regenerate from ``python/`` with::

    python -m optiqal.data_build.meps_quality_weights

Seven age anchors, the within-age standard deviation, and six condition
decrements are rounded to three decimals from
``data/meps/quality_weight_calibration.json``. The age-95 anchor is not in
MEPS; it is the authored extrapolation used by the engine before snapshots and
is identified as such in the output provenance.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

from optiqal.data_build._common import file_checksum, render_snapshot, write_snapshot

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CALIBRATION_PATH = PACKAGE_ROOT / "data" / "meps" / "quality_weight_calibration.json"
SNAPSHOT_PATH = PACKAGE_ROOT / "data" / "snapshots" / "meps_quality_weights.json"

AGE_BAND_TO_ANCHOR = (
    ("(18, 30]", 25),
    ("(30, 40]", 35),
    ("(40, 50]", 45),
    ("(50, 60]", 55),
    ("(60, 70]", 65),
    ("(70, 80]", 75),
    ("(80, 100]", 85),
)
CONDITION_KEYS = (
    "diabetes",
    "hypertension",
    "heart_disease",
    "stroke",
    "cancer",
    "arthritis",
)


class CalibrationError(ValueError):
    """The committed MEPS calibration lacks a required numeric value."""


def _node(calibration: dict, *path: str) -> Any:
    node: Any = calibration
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise CalibrationError(f"missing calibration field {'.'.join(path)}")
        node = node[key]
    return node


def _rounded(calibration: dict, *path: str) -> float:
    value = _node(calibration, *path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationError(f"calibration field {'.'.join(path)} is not numeric")
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise CalibrationError(
            f"calibration field {'.'.join(path)} must be finite and non-negative"
        )
    return round(value, 3)


def build_data(calibration: dict) -> dict:
    """Derive the exact runtime data block from a calibration object."""
    quality_weights = {
        str(age): _rounded(calibration, "by_age", "mean", age_band)
        for age_band, age in AGE_BAND_TO_ANCHOR
    }
    quality_weights["95"] = 0.75

    condition_decrements = {
        condition: _rounded(calibration, "by_condition", condition, "decrement")
        for condition in CONDITION_KEYS
    }
    return {
        "quality_weights": quality_weights,
        "quality_weight_std": _rounded(calibration, "within_age_std"),
        "condition_decrements": condition_decrements,
    }


def build_provenance(calibration_path: Path) -> dict:
    """Describe the empirical and authored inputs without overstating retrieval."""
    return {
        "source": (
            "Committed AHRQ MEPS 2019-2022 quality_weight_calibration.json; "
            "age 95 is an authored extrapolation transcribed from lifecycle.py"
        ),
        "url": "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files.jsp",
        "table": (
            "by_age.mean, within_age_std, and by_condition.*.decrement; "
            "AHRQ HC-209, HC-216, HC-224, and HC-233"
        ),
        "retrieved": "2026-09-04",
        "generator": "python -m optiqal.data_build.meps_quality_weights",
        "version": 1,
        "source_artifact": "optiqal/data/meps/quality_weight_calibration.json",
        "source_artifact_sha256": file_checksum(calibration_path),
        "retrieval_note": (
            "The committed artifact and source URLs were verified on this date; "
            "the original AHRQ download date was not recorded."
        ),
        "mapping": "SF-12 PCS/MCS to EQ-5D, Franks et al. 2004",
        "rounding": "Derived runtime values are rounded to three decimals.",
    }


def _load_calibration(calibration_path: Path) -> dict:
    try:
        calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalibrationError(f"cannot read {calibration_path}: {exc}") from exc
    if not isinstance(calibration, dict):
        raise CalibrationError(f"{calibration_path} is not a JSON object")
    return calibration


def render_quality_weight_snapshot(
    calibration_path: Path = CALIBRATION_PATH,
) -> str:
    """Render the snapshot bytes this generator would write."""
    calibration = _load_calibration(calibration_path)
    return render_snapshot(build_provenance(calibration_path), build_data(calibration))


def write_quality_weight_snapshot(
    calibration_path: Path = CALIBRATION_PATH,
    output_path: Path = SNAPSHOT_PATH,
) -> Path:
    """Build and write the runtime snapshot from a calibration JSON file."""
    calibration = _load_calibration(calibration_path)
    return write_snapshot(
        output_path,
        build_provenance(calibration_path),
        build_data(calibration),
    )


def check_quality_weight_snapshot(
    calibration_path: Path = CALIBRATION_PATH,
    output_path: Path = SNAPSHOT_PATH,
) -> bool:
    """Report whether the committed snapshot is byte-identical to a rebuild."""
    expected = render_quality_weight_snapshot(calibration_path)
    try:
        actual = output_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return actual == expected


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Regenerate the committed quality-weight snapshot, or check it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare the committed snapshot with a rebuild and write nothing",
    )
    args = parser.parse_args(argv)

    if args.check:
        if check_quality_weight_snapshot():
            print(f"{SNAPSHOT_PATH} is byte-identical to a rebuild.")
            return
        print(
            f"{SNAPSHOT_PATH} differs from a rebuild; run this module without --check.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    output_path = write_quality_weight_snapshot()
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
