"""Regression checks for snapshot sleep inputs (A1-A4)."""

import sqlite3
from dataclasses import replace

import pytest

from optiqal.protocol_ground_up import load_baseline, resolve_protocol_context
from optiqal.sleep_baseline import (
    MIN_EIGHT_NIGHTS,
    duration_for_construct,
    measured_duration_hours,
    sleep_window,
)


@pytest.fixture
def snapshot(tmp_path):
    # Never mutate the personal database; copy the synthetic fixture to SQLite.
    context = resolve_protocol_context(None)
    source = sqlite3.connect(f"file:{context.health_db}?mode=ro", uri=True)
    path = tmp_path / "snapshot.sqlite"
    conn = sqlite3.connect(path)
    source.backup(conn)
    source.close()
    # A historical snapshot must still have full windows when run today.
    conn.execute("UPDATE sleep_nights SET date=date(date, '-10 year')")
    conn.execute("UPDATE body_comp SET date=date(date, '-10 year')")
    conn.execute(
        "UPDATE sleep_nights SET whoop_sleep_hours=9, whoop_light_min=180, "
        "whoop_deep_min=60, whoop_rem_min=120, eight_sleep_min=390, "
        "eight_social_jetlag_min=CASE WHEN CAST(substr(date, 9, 2) AS INT)%2 "
        "THEN -60 ELSE 60 END"
    )
    conn.commit()
    yield conn, replace(context, health_db=path)
    conn.close()


def test_duration_uses_asleep_columns_and_explicit_construct(snapshot):
    conn, context = snapshot
    calibrated = load_baseline(context)
    measured = load_baseline(replace(context, duration_construct="measured"))
    assert calibrated["sleep_90d"]["whoop_sleep_h"] == 6
    assert calibrated["derived"]["measured_sleep_h_90d"] == 6.25
    assert calibrated["derived"]["combined_sleep_h_90d"] == 7.05
    assert measured["derived"]["combined_sleep_h_90d"] == 6.25
    assert calibrated["derived"]["calibrated_self_report_duration_burden"] == 0
    assert calibrated["derived"]["measured_duration_burden"] == 0.5
    assert measured["derived"]["sleep_component_burdens"]["duration"] == 0.5
    assert (
        calibrated["window_anchor_date"]
        == conn.execute("SELECT MAX(date) FROM sleep_nights").fetchone()[0]
    )
    assert calibrated["sleep_90d"]["nights"] == 91
    assert calibrated["sleep_30d"]["nights"] == 31
    assert calibrated["training_180d"]["days"] == 181
    assert calibrated["body_comp_180d"]["days"] > 0
    assert calibrated["sleep_90d"]["eight_social_jetlag"] == 60


def test_eight_breathing_and_stale_debt_are_inert_and_no_trial_is_invented(snapshot):
    conn, context = snapshot
    before = load_baseline(context)
    conn.execute(
        "UPDATE sleep_nights SET eight_breathing_score=0.01, eight_sleep_debt_min=9999"
    )
    conn.commit()
    after = load_baseline(context)
    assert after == before
    assert after["derived"]["airway_response_signal"] == 0
    assert "No dated" in after["derived"]["airway_response_note"]
    assert "airway_trial_windows" not in after


def test_sparse_eight_components_fall_back_independently(snapshot):
    conn, context = snapshot
    conn.execute(
        "UPDATE sleep_nights SET eight_sleep_min=NULL, eight_quality_score=NULL"
    )
    conn.execute(
        "UPDATE sleep_nights SET eight_sleep_min=480, eight_quality_score=0 "
        "WHERE date IN (SELECT date FROM sleep_nights ORDER BY date DESC LIMIT ?)",
        (MIN_EIGHT_NIGHTS - 1,),
    )
    conn.commit()
    baseline = load_baseline(context)
    assert baseline["sleep_90d"]["eight_sleep_h"] is None
    assert baseline["derived"]["measured_sleep_h_90d"] == 6
    assert baseline["sleep_90d"]["eight_quality"] is None
    assert baseline["derived"]["sleep_component_burdens"]["quality"] == 0
    assert baseline["sleep_90d"]["eight_waso"] == 20
    conn.execute(
        "UPDATE sleep_nights SET eight_quality_score=0 "
        "WHERE date IN (SELECT date FROM sleep_nights ORDER BY date DESC LIMIT ?)",
        (MIN_EIGHT_NIGHTS,),
    )
    conn.commit()
    assert load_baseline(context)["derived"]["sleep_component_burdens"]["quality"] == 1


def test_empty_windows_preserve_none(snapshot):
    conn, context = snapshot
    conn.execute("DELETE FROM sleep_nights")
    conn.commit()
    baseline = load_baseline(context)
    assert baseline["window_anchor_date"] is None
    assert baseline["sleep_90d"]["nights"] == 0
    assert baseline["sleep_90d"]["whoop_sleep_h"] is None
    assert baseline["derived"]["combined_sleep_h_90d"] is None
    assert baseline["derived"]["measured_sleep_h_90d"] is None
    assert baseline["derived"]["sleep_component_burdens"]["duration"] == 0


def test_duration_validation_and_missing_devices(snapshot):
    conn, _ = snapshot
    conn.row_factory = sqlite3.Row
    assert measured_duration_hours(sleep_window(conn, None, 90)) is None
    assert measured_duration_hours({"whoop_sleep_h": None, "eight_sleep_h": 7}) == 7
    assert duration_for_construct(None, "measured") is None
    with pytest.raises(ValueError, match="duration construct"):
        duration_for_construct(7, "invalid")


def test_gate_override_survives_payload_reconstruction(snapshot):
    from optiqal.protocol_ground_up import protocol_sleep_estimate_from_baseline_dict

    _, context = snapshot
    baseline = load_baseline(replace(context, breathing_mortality_gate_override=0.5))
    estimate = protocol_sleep_estimate_from_baseline_dict(baseline)
    assert baseline["derived"]["sleep_breathing_mortality_gate"] == 0.5
    assert estimate.breathing_mortality_gate == 0.5
