"""Shared pytest fixtures.

The protocol-ground-up code defaults to reading a personal health database at
``~/clawd/data/health.db`` (Max's machine). That file does not exist in CI or
on other contributors' machines, so the protocol tests used to fail there with
``sqlite3.OperationalError: unable to open database file``.

This builds a small synthetic health DB with the schema/columns the protocol
loader queries, populated with neutral (non-personal) values, and points the
default protocol context at it via ``OPTIQAL_HEALTH_DB`` for the whole session.
It contains no real personal data — only deterministic synthetic rows.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta

# Columns load_baseline() reads from sleep_nights (a subset of the real schema).
_SLEEP_COLUMNS = [
    "whoop_recovery",
    "whoop_rhr",
    "whoop_hrv",
    "whoop_spo2",
    "whoop_strain",
    "whoop_sleep_hours",
    "whoop_sleep_perf",
    "eight_score",
    "eight_quality_score",
    "eight_routine_score",
    "eight_sleep_min",
    "eight_waso_min",
    "eight_latency_min",
    "eight_breathing_score",
    "eight_social_jetlag_min",
    "eight_snore_pct",
    "eight_sleep_debt_min",
]


def _build_synthetic_health_db(path: str) -> None:
    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.execute(
        "CREATE TABLE sleep_nights (date TEXT PRIMARY KEY, "
        + ", ".join(f"{col} REAL" for col in _SLEEP_COLUMNS)
        + ")"
    )
    cur.execute("CREATE TABLE bloodwork (date TEXT, marker TEXT, value REAL)")
    cur.execute(
        "CREATE TABLE body_comp (date TEXT, weight_kg REAL, body_fat_pct REAL, "
        "muscle_mass_kg REAL, source TEXT)"
    )

    # 200 nights of deterministic, neutral synthetic sleep data ending today.
    today = date.today()
    row_values = {
        "whoop_recovery": 60.0,
        "whoop_rhr": 50.0,
        "whoop_hrv": 90.0,
        "whoop_spo2": 96.0,
        "whoop_strain": 12.0,
        "whoop_sleep_hours": 7.0,
        "whoop_sleep_perf": 85.0,
        "eight_score": 80.0,
        "eight_quality_score": 80.0,
        "eight_routine_score": 80.0,
        "eight_sleep_min": 420.0,
        "eight_waso_min": 20.0,
        "eight_latency_min": 12.0,
        "eight_breathing_score": 0.95,
        "eight_social_jetlag_min": 20.0,
        "eight_snore_pct": 2.0,
        "eight_sleep_debt_min": 30.0,
    }
    placeholders = ", ".join(["?"] * (1 + len(_SLEEP_COLUMNS)))
    insert_sql = (
        "INSERT INTO sleep_nights (date, "
        + ", ".join(_SLEEP_COLUMNS)
        + f") VALUES ({placeholders})"
    )
    for offset in range(200):
        day = (today - timedelta(days=offset)).isoformat()
        cur.execute(insert_sql, [day, *[row_values[c] for c in _SLEEP_COLUMNS]])

    # Neutral synthetic bloodwork (NOT real personal values).
    markers = {
        "LDL": 90.0,
        "HDL": 55.0,
        "Triglycerides": 100.0,
        "HbA1c": 5.2,
        "Glucose": 90.0,
        "Vitamin D": 45.0,
        "TSH": 1.5,
        "eGFR": 90.0,
        "Creatinine": 1.0,
    }
    for marker, value in markers.items():
        cur.execute(
            "INSERT INTO bloodwork (date, marker, value) VALUES (?, ?, ?)",
            (today.isoformat(), marker, value),
        )

    # Clearly-lean synthetic body comp (BMI ~21.5 at the model's 1.78m default)
    # so the "lean low-risk" GLP-1 harm-dominated property holds unambiguously.
    for offset in range(0, 200, 30):
        day = (today - timedelta(days=offset)).isoformat()
        cur.execute(
            "INSERT INTO body_comp (date, weight_kg, body_fat_pct, muscle_mass_kg, "
            "source) VALUES (?, ?, ?, ?, ?)",
            (day, 68.0, 14.0, 34.0, "synthetic"),
        )

    conn.commit()
    conn.close()


def pytest_configure(config):
    """Point protocol-context loaders at a synthetic DB unless one is set.

    Done in ``pytest_configure`` (not a session fixture) so it runs once per
    process *before* any test — including in each pytest-xdist worker, which a
    session-scoped autouse fixture races with. Respects an existing
    OPTIQAL_HEALTH_DB (e.g. a developer pointing at real data).
    """
    if os.environ.get("OPTIQAL_HEALTH_DB"):
        return

    # Per-process file under pytest's basetemp so xdist workers don't collide
    # and the path is stable for the life of the process.
    import tempfile

    db_dir = tempfile.mkdtemp(prefix="optiqal-health-")
    db_path = os.path.join(db_dir, "synthetic_health.db")
    _build_synthetic_health_db(db_path)
    os.environ["OPTIQAL_HEALTH_DB"] = db_path
