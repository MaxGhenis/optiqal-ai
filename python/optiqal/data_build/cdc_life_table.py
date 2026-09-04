"""Validate the transcribed life-table snapshot and its source comparison.

Run from ``python/`` with::

    python -m optiqal.data_build.cdc_life_table

The production anchors do not match the CDC publication historically cited by
the engine, so this module deliberately does not pretend it can fetch and
regenerate them. It pins the behavior-preserving snapshot and the committed
comparison to independent checksums, verifies every comparison row, and prints
the manual steps for refreshing the published-source evidence.
"""

from __future__ import annotations

from pathlib import Path

from optiqal.snapshots import SnapshotError, data_checksum, load_snapshot

SNAPSHOT_NAME = "cdc_life_table"
COMPARISON_NAME = "cdc_life_table_2021_source_comparison"
EXPECTED_SNAPSHOT_DATA_SHA256 = (
    "c760c03f4cffc93b606f1b75ce0a13e32d5709ee1da52913ee9dd20e42d04cd2"
)
EXPECTED_COMPARISON_DATA_SHA256 = (
    "a7d0c35126bb8f3559f220613c81d5dbb984fd5b90c9cc4290c1e49256f72c54"
)
EXPECTED_AGES = (
    0,
    1,
    5,
    10,
    15,
    20,
    25,
    30,
    35,
    40,
    45,
    50,
    55,
    60,
    65,
    70,
    75,
    80,
    85,
    90,
    95,
    100,
)


def _fail(path: Path, message: str) -> None:
    raise SnapshotError(f"{path}: {message}")


def validate_committed_artifacts() -> None:
    """Validate pinned data and every mechanically computed comparison cell."""
    snapshot = load_snapshot(SNAPSHOT_NAME)
    if data_checksum(snapshot.data) != EXPECTED_SNAPSHOT_DATA_SHA256:
        _fail(snapshot.path, "data does not match the pinned transcribed checksum")

    life_table = {}
    for sex in ("male", "female"):
        table = snapshot.age_table("life_table", sex, maximum=1.0)
        if tuple(table) != EXPECTED_AGES:
            _fail(snapshot.path, f"data.life_table.{sex} has unexpected anchor ages")
        life_table[sex] = table

    comparison = load_snapshot(COMPARISON_NAME)
    if data_checksum(comparison.data) != EXPECTED_COMPARISON_DATA_SHA256:
        _fail(comparison.path, "data does not match the pinned source comparison")

    rows = comparison.data.get("rows")
    if not isinstance(rows, dict) or set(rows) != {"male", "female"}:
        _fail(comparison.path, "data.rows must contain male and female tables")

    exact_matches = 0
    ratios = []
    for sex in ("male", "female"):
        if not isinstance(rows[sex], dict):
            _fail(comparison.path, f"data.rows.{sex} is not an object")
        if tuple(int(age) for age in rows[sex]) != EXPECTED_AGES:
            _fail(comparison.path, f"data.rows.{sex} has unexpected anchor ages")
        for age, snapshot_qx in life_table[sex].items():
            row = rows[sex].get(str(age))
            if not isinstance(row, dict):
                _fail(comparison.path, f"missing data.rows.{sex}.{age}")
            published_qx = row.get("published_qx")
            if isinstance(published_qx, bool) or not isinstance(
                published_qx, (int, float)
            ):
                _fail(
                    comparison.path,
                    f"data.rows.{sex}.{age}.published_qx is not numeric",
                )
            expected_delta = round(snapshot_qx - published_qx, 6)
            expected_ratio = round(snapshot_qx / published_qx, 12)
            expected = {
                "snapshot_qx": snapshot_qx,
                "published_qx": published_qx,
                "delta_snapshot_minus_published": expected_delta,
                "ratio_snapshot_to_published": expected_ratio,
            }
            if row != expected:
                _fail(comparison.path, f"data.rows.{sex}.{age} is inconsistent")
            exact_matches += snapshot_qx == published_qx
            if age != 100:
                ratios.append((expected_ratio, sex, age))

    summary = comparison.data.get("summary")
    if not isinstance(summary, dict):
        _fail(comparison.path, "data.summary is not an object")
    if summary.get("matches_source") is not False:
        _fail(comparison.path, "data.summary must record the source mismatch")
    if summary.get("anchors_compared") != 44 or exact_matches != 0:
        _fail(comparison.path, "comparison must cover 44 anchors with no exact matches")
    if summary.get("exact_matches") != exact_matches:
        _fail(comparison.path, "data.summary.exact_matches is inconsistent")

    minimum = min(ratios)
    maximum = max(ratios)
    for label, expected_row in (("minimum_ratio", minimum), ("maximum_ratio", maximum)):
        summary_row = summary.get(label)
        if not isinstance(summary_row, dict):
            _fail(comparison.path, f"data.summary.{label} is not an object")
        if (
            summary_row.get("ratio"),
            summary_row.get("sex"),
            summary_row.get("age"),
        ) != expected_row:
            _fail(comparison.path, f"data.summary.{label} is inconsistent")


def print_manual_regeneration_steps() -> None:
    """Print the source-refresh process without claiming an automatic fetch."""
    print("Manual source-comparison refresh (the generator does not fetch CDC data):")
    print(
        "1. Download NVSR 72-12 Table02.xlsx and Table03.xlsx from "
        "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/NVSR/72-12/."
    )
    print(
        "2. Transcribe the qx column at ages 0, 1, 5, ..., 100 into "
        f"{COMPARISON_NAME}.json and recompute each delta and ratio."
    )
    print("3. Treat age 100 as CDC's open-ended '100 and older' row with qx=1.000000.")
    print(
        "4. Update the pinned comparison checksum after source review; changing the "
        "runtime snapshot belongs in a separate number-changing PR."
    )


def main() -> None:
    """Validate committed artifacts and explain how to refresh source evidence."""
    validate_committed_artifacts()
    print("Validated the transcribed CDC snapshot and NVSR 72-12 comparison.")
    print_manual_regeneration_steps()


if __name__ == "__main__":
    main()
