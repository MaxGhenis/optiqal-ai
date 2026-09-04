"""Tests for provenance-stamped runtime data snapshots."""

import importlib
import json
import shutil
from pathlib import Path

import pytest

import optiqal.lifecycle as lifecycle
from optiqal import snapshots
from optiqal.data_build import cause_fractions, cdc_life_table, meps_quality_weights


def _snapshot(data: dict) -> dict:
    return {
        "provenance": {
            "source": "test source",
            "url": "https://example.test/source",
            "table": "test table",
            "retrieved": "2026-09-04",
            "generator": "python -m optiqal.data_build.test",
            "version": 1,
            "sha256_of_data": snapshots.data_checksum(data),
        },
        "data": data,
    }


@pytest.fixture
def snapshot_directory(tmp_path, monkeypatch):
    """Point the loader at an isolated directory and reset its cache."""
    snapshots.clear_cache()
    monkeypatch.setattr(snapshots, "snapshot_dir", lambda: tmp_path)
    yield tmp_path
    snapshots.clear_cache()


def _write(directory, name: str, payload: dict) -> None:
    (directory / f"{name}.json").write_text(json.dumps(payload))


def test_missing_snapshot_fails_closed_and_names_file(snapshot_directory):
    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("missing")

    assert "missing.json" in str(error.value)


def test_missing_provenance_fails_closed_and_names_file(snapshot_directory):
    _write(snapshot_directory, "no_provenance", {"data": {"rates": {"1": 0.1}}})

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("no_provenance")

    assert "no_provenance.json" in str(error.value)
    assert "provenance" in str(error.value)


def test_nan_fails_closed_and_names_file(snapshot_directory):
    payload = _snapshot({"rates": {"1": 0.1}})
    payload["data"]["rates"]["1"] = float("nan")
    _write(snapshot_directory, "nan", payload)

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("nan")

    assert "nan.json" in str(error.value)
    assert "non-finite" in str(error.value)


def test_negative_rate_fails_closed_and_names_file(snapshot_directory):
    _write(snapshot_directory, "negative", _snapshot({"rates": {"1": -0.1}}))

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("negative").age_table("rates")

    assert "negative.json" in str(error.value)
    assert "negative" in str(error.value)


def test_non_monotone_ages_fail_closed_and_name_file(snapshot_directory):
    _write(
        snapshot_directory,
        "ages",
        _snapshot({"rates": {"10": 0.1, "5": 0.05}}),
    )

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("ages").age_table("rates")

    assert "ages.json" in str(error.value)
    assert "not strictly increasing" in str(error.value)


def test_noncanonical_age_fails_closed_and_names_file(snapshot_directory):
    _write(snapshot_directory, "age_spelling", _snapshot({"rates": {"01": 0.1}}))

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("age_spelling").age_table("rates")

    assert "age_spelling.json" in str(error.value)
    assert "non-canonical" in str(error.value)


def test_checksum_mismatch_fails_closed_and_names_file(snapshot_directory):
    payload = _snapshot({"rates": {"1": 0.1}})
    payload["data"]["rates"]["1"] = 0.2
    _write(snapshot_directory, "checksum", payload)

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("checksum")

    assert "checksum.json" in str(error.value)
    assert "sha256_of_data" in str(error.value)


def test_canonical_json_hashes_int_and_float_spellings_alike():
    """``1`` and ``1.0`` are one value to the loader, so one checksum."""
    integer_spelling = {"rows": {"1": 1, "2": 0}, "flag": True, "count": 44}
    float_spelling = {"rows": {"1": 1.0, "2": 0.0}, "flag": True, "count": 44.0}

    assert snapshots.canonical_json(integer_spelling) == snapshots.canonical_json(
        float_spelling
    )
    assert snapshots.data_checksum(integer_spelling) == snapshots.data_checksum(
        float_spelling
    )


def test_canonical_json_keeps_booleans_out_of_the_numeric_coercion():
    """``True`` must not canonicalize to ``1.0``; the audit rows carry flags."""
    assert snapshots.canonical_json({"flag": True}) != snapshots.canonical_json(
        {"flag": 1}
    )
    assert snapshots.canonical_json({"flag": False}) != snapshots.canonical_json(
        {"flag": 0}
    )


def test_int_and_float_spellings_load_under_one_committed_checksum(
    snapshot_directory,
):
    """The equality holds end to end: either spelling passes the same pin."""
    checksum = snapshots.data_checksum({"rates": {"1": 1.0}})
    payload = _snapshot({"rates": {"1": 1.0}})
    payload["data"]["rates"]["1"] = 1
    _write(snapshot_directory, "spelling", payload)

    loaded = snapshots.load_snapshot("spelling")

    assert loaded.provenance["sha256_of_data"] == checksum
    assert loaded.age_table("rates", maximum=1.0) == {1: 1.0}


def test_meps_snapshot_matches_committed_calibration():
    calibration_path = meps_quality_weights.CALIBRATION_PATH
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    expected = meps_quality_weights.build_data(calibration)

    actual = snapshots.load_snapshot("meps_quality_weights")

    assert actual.data == expected
    assert actual.provenance[
        "source_artifact_sha256"
    ] == meps_quality_weights.file_checksum(calibration_path)


def test_cdc_life_table_snapshot_and_source_comparison_are_pinned():
    cdc_life_table.validate_committed_artifacts()


def test_cause_fraction_snapshot_is_pinned():
    cause_fractions.validate_committed_snapshot()


def _assert_nested_close(actual, expected, path: str = "fixture") -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        actual_by_json_key = {str(key): value for key, value in actual.items()}
        assert actual_by_json_key.keys() == expected.keys(), path
        for key, expected_value in expected.items():
            _assert_nested_close(
                actual_by_json_key[key], expected_value, f"{path}.{key}"
            )
        return
    assert isinstance(actual, (int, float)), path
    assert actual == pytest.approx(expected, rel=0, abs=1e-12), path


def test_loaded_lifecycle_values_match_pre_refactor_literals():
    fixture_path = (
        Path(__file__).parent / "fixtures" / "lifecycle_constants_2026-09-04.json"
    )
    expected = json.loads(fixture_path.read_text(encoding="utf-8"))
    actual = {
        "CDC_LIFE_TABLE": lifecycle.CDC_LIFE_TABLE,
        "CAUSE_FRACTIONS": lifecycle.CAUSE_FRACTIONS,
        "QUALITY_WEIGHTS": lifecycle.QUALITY_WEIGHTS,
        "QUALITY_WEIGHT_STD": lifecycle.QUALITY_WEIGHT_STD,
        "CONDITION_DECREMENTS": lifecycle.CONDITION_DECREMENTS,
    }

    _assert_nested_close(actual, expected)
    assert isinstance(lifecycle.QUALITY_WEIGHT_STD, float)


def test_bad_snapshot_fails_during_lifecycle_import(tmp_path, monkeypatch):
    real_snapshot_dir = snapshots.snapshot_dir()
    runtime_names = ("cdc_life_table", "cause_fractions", "meps_quality_weights")
    for name in runtime_names:
        shutil.copy2(real_snapshot_dir / f"{name}.json", tmp_path / f"{name}.json")

    bad_path = tmp_path / "cdc_life_table.json"
    payload = json.loads(bad_path.read_text(encoding="utf-8"))
    payload["data"]["life_table"]["male"]["0"] = -0.00566
    payload["provenance"]["sha256_of_data"] = snapshots.data_checksum(payload["data"])
    bad_path.write_text(json.dumps(payload), encoding="utf-8")

    try:
        with monkeypatch.context() as context:
            context.setattr(snapshots, "snapshot_dir", lambda: tmp_path)
            snapshots.clear_cache()
            with pytest.raises(snapshots.SnapshotError) as error:
                importlib.reload(lifecycle)
            assert "cdc_life_table.json" in str(error.value)
            assert "negative" in str(error.value)
    finally:
        snapshots.clear_cache()
        importlib.reload(lifecycle)
