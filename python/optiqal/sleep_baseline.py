"""Snapshot-anchored wearable inputs and explicit sleep-duration constructs."""

from __future__ import annotations

import sqlite3
from typing import Literal

DurationConstruct = Literal["calibrated_self_report", "measured"]

# Lauderdale et al. (2008), PMID 18854708, abstract fetched 2026-09-23:
# CARDIA mean actigraphy sleep was 6.0 h versus 6.8 h self-reported.
# https://pubmed.ncbi.nlm.nih.gov/18854708/
# Judgment: transport the mean 0.8 h difference to both wearables so their
# duration is comparable with the self-report construct of the 7 h threshold.
# This population offset is not an individual calibration of either device.
MEASURED_TO_SELF_REPORT_OFFSET_H = 0.8

# Judgment: require ten observed nights for each Eight metric in a window;
# fewer observations are too sparse to personalize that component reliably.
MIN_EIGHT_NIGHTS = 10

EIGHT_SLEEP_COLUMNS = {
    "eight_score": "eight_score",
    "eight_quality": "eight_quality_score",
    "eight_routine": "eight_routine_score",
    "eight_sleep_h": "eight_sleep_min / 60.0",
    "eight_waso": "eight_waso_min",
    "eight_latency": "eight_latency_min",
    "eight_social_jetlag": "ABS(eight_social_jetlag_min)",
    "eight_snore_pct": "eight_snore_pct",
}
WHOOP_ASLEEP_HOURS_SQL = "(whoop_light_min + whoop_deep_min + whoop_rem_min) / 60.0"


def sleep_window(conn: sqlite3.Connection, anchor_date: str | None, days: int) -> dict:
    """Read a window without turning missing observations into zeroes.

    Count each Eight metric independently: a device night with missing WASO
    must not make that component pass the coverage threshold.
    """
    aggregates = [
        "COUNT(*) AS nights",
        f"AVG({WHOOP_ASLEEP_HOURS_SQL}) AS whoop_sleep_h",
        "AVG(whoop_sleep_perf) AS whoop_sleep_perf",
        "AVG(whoop_recovery) AS whoop_recovery",
        "AVG(whoop_spo2) AS whoop_spo2",
    ]
    for name, expression in EIGHT_SLEEP_COLUMNS.items():
        aggregates.extend(
            [
                f"COUNT({expression}) AS {name}_nights",
                f"CASE WHEN COUNT({expression}) >= {MIN_EIGHT_NIGHTS} "
                f"THEN AVG({expression}) END AS {name}",
            ]
        )
    row = conn.execute(
        "SELECT "
        + ", ".join(aggregates)
        + " FROM sleep_nights WHERE date >= date(?, ?) AND date <= ?",
        (anchor_date, f"-{days} day", anchor_date),
    ).fetchone()
    return dict(row)


def measured_duration_hours(window: dict) -> float | None:
    values = [
        float(window[key])
        for key in ("whoop_sleep_h", "eight_sleep_h")
        if window.get(key) is not None
    ]
    return sum(values) / len(values) if values else None


def duration_for_construct(
    measured: float | None, construct: DurationConstruct
) -> float | None:
    if construct not in ("measured", "calibrated_self_report"):
        raise ValueError(f"Unknown duration construct: {construct}")
    if measured is None:
        return None
    return measured + (
        MEASURED_TO_SELF_REPORT_OFFSET_H
        if construct == "calibrated_self_report"
        else 0.0
    )


def rounded_window(window: dict) -> dict:
    return {
        key: (
            value
            if value is None or key == "nights" or key.endswith("_nights")
            else round(float(value), 2 if key.endswith("_h") else 1)
        )
        for key, value in window.items()
    }
