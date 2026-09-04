"""Validate the hand-transcribed cause-fraction approximation.

Run from ``python/`` with::

    python -m optiqal.data_build.cause_fractions

No saved CDC WONDER query, export, table identifier, or exact cause definition
survives in the repository. Automatic source regeneration would therefore
invent missing provenance. This module pins and validates the committed values
and prints the evidence that a future, number-changing replacement must record.
"""

from __future__ import annotations

from optiqal.snapshots import SnapshotError, data_checksum, load_snapshot

SNAPSHOT_NAME = "cause_fractions"
EXPECTED_DATA_SHA256 = (
    "e653f6864d8fc5c537e6ca5783932982dea7e11487a2c54e90da5b1111dfcb0c"
)
EXPECTED_AGES = (40, 50, 60, 70, 80, 90)
CAUSES = ("cvd", "cancer", "other")


def validate_committed_snapshot() -> None:
    """Validate the pinned approximation, age order, columns, and row sums."""
    snapshot = load_snapshot(SNAPSHOT_NAME)
    if data_checksum(snapshot.data) != EXPECTED_DATA_SHA256:
        raise SnapshotError(
            f"{snapshot.path}: data does not match the pinned transcribed checksum"
        )
    rows = snapshot.age_rows(
        "cause_fractions", columns=CAUSES, sums_to=1.0, tolerance=1e-12
    )
    if tuple(rows) != EXPECTED_AGES:
        raise SnapshotError(
            f"{snapshot.path}: data.cause_fractions has unexpected anchor ages"
        )


def print_manual_regeneration_steps() -> None:
    """Describe a reproducible future WONDER derivation without inventing one."""
    print("Manual source replacement (automatic regeneration is impossible):")
    print(
        "1. Record the CDC WONDER dataset/release, year 2021, and population filters."
    )
    print("2. Record the exact age grouping and numerator cause definitions.")
    print("3. Commit the saved query parameters and exported raw death counts.")
    print("4. Compute CVD, cancer, and other shares and document their row-sum checks.")
    print(
        "5. Replace this pinned approximation only in an explicit number-changing PR."
    )


def main() -> None:
    """Validate the snapshot and explain the manual replacement process."""
    validate_committed_snapshot()
    print("Validated the transcribed cause-fraction snapshot against its checksum.")
    print_manual_regeneration_steps()


if __name__ == "__main__":
    main()
