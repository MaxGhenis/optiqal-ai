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


def test_overflowing_float_literal_fails_closed_and_names_file(snapshot_directory):
    """``1e400`` is valid JSON grammar; it parses to ``inf``, not a constant.

    ``parse_constant`` never sees it, so the guard against bare ``NaN`` and
    ``Infinity`` tokens does not catch it and the value reaches the checksum.
    """
    raw = json.dumps(
        {
            "provenance": {
                "source": "test source",
                "url": "https://example.test/source",
                "table": "test table",
                "retrieved": "2026-09-04",
                "generator": "python -m optiqal.data_build.test",
                "version": 1,
                "sha256_of_data": "0" * 64,
            },
            "data": {"rates": {"1": 0.1}},
        }
    ).replace('"1": 0.1', '"1": 1e400')
    (snapshot_directory / "overflow.json").write_text(raw)

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("overflow")

    assert "overflow.json" in str(error.value)
    assert "canonically serialized" in str(error.value)


def test_age_table_rejects_a_missing_age_and_names_file(snapshot_directory):
    """A one-row table used to satisfy every age check the loader had."""
    _write(snapshot_directory, "short_ages", _snapshot({"rates": {"5": 0.05}}))

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("short_ages").age_table("rates", ages=(5, 10, 15))

    assert "short_ages.json" in str(error.value)
    assert "ages are (5,), expected (5, 10, 15)" in str(error.value)


def test_age_table_rejects_an_extra_age_and_names_file(snapshot_directory):
    _write(
        snapshot_directory,
        "long_ages",
        _snapshot({"rates": {"5": 0.05, "10": 0.1, "12": 0.12, "15": 0.15}}),
    )

    with pytest.raises(snapshots.SnapshotError) as error:
        snapshots.load_snapshot("long_ages").age_table("rates", ages=(5, 10, 15))

    assert "long_ages.json" in str(error.value)
    assert "ages are (5, 10, 12, 15), expected (5, 10, 15)" in str(error.value)


def test_age_table_without_a_pin_still_accepts_any_increasing_ages(
    snapshot_directory,
):
    """The pin is opt-in; unpinned callers keep the previous behaviour."""
    _write(snapshot_directory, "free_ages", _snapshot({"rates": {"5": 0.05}}))

    assert snapshots.load_snapshot("free_ages").age_table("rates") == {5: 0.05}


def test_life_table_age_pin_matches_the_generator_pin():
    """lifecycle.py and the standalone validator must name one age set."""
    assert lifecycle.LIFE_TABLE_AGES == cdc_life_table.EXPECTED_AGES


def test_runtime_age_pins_match_the_committed_snapshots():
    assert tuple(lifecycle.CDC_LIFE_TABLE["male"]) == lifecycle.LIFE_TABLE_AGES
    assert tuple(lifecycle.CDC_LIFE_TABLE["female"]) == lifecycle.LIFE_TABLE_AGES
    assert tuple(lifecycle.QUALITY_WEIGHTS) == lifecycle.QUALITY_WEIGHT_AGES
    assert len(lifecycle.LIFE_TABLE_AGES) == 22
    assert len(lifecycle.QUALITY_WEIGHT_AGES) == 8


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


def test_meps_check_mode_confirms_the_committed_bytes():
    """--check must compare, and must not be the write path in disguise."""
    before = meps_quality_weights.SNAPSHOT_PATH.read_bytes()

    assert meps_quality_weights.check_quality_weight_snapshot() is True
    meps_quality_weights.main(["--check"])

    assert meps_quality_weights.SNAPSHOT_PATH.read_bytes() == before


def test_meps_check_mode_detects_drift(tmp_path):
    drifted = tmp_path / "meps_quality_weights.json"
    payload = json.loads(meps_quality_weights.SNAPSHOT_PATH.read_text(encoding="utf-8"))
    payload["data"]["quality_weights"]["25"] = 0.5
    drifted.write_text(json.dumps(payload), encoding="utf-8")

    assert meps_quality_weights.check_quality_weight_snapshot(output_path=drifted) is (
        False
    )
    assert (
        meps_quality_weights.check_quality_weight_snapshot(
            output_path=tmp_path / "absent.json"
        )
        is False
    )


def test_generator_check_flags_are_parsed_not_ignored():
    """A silently swallowed --check once let a dry run rewrite the snapshot."""
    for module in (cause_fractions, cdc_life_table, meps_quality_weights):
        with pytest.raises(SystemExit):
            module.main(["--nonexistent-flag"])


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


def _reload_lifecycle_against(tmp_path, monkeypatch, name: str, mutate) -> str:
    """Copy the real snapshots, mutate one, and reload lifecycle against them."""
    real_snapshot_dir = snapshots.snapshot_dir()
    for runtime_name in ("cdc_life_table", "cause_fractions", "meps_quality_weights"):
        shutil.copy2(
            real_snapshot_dir / f"{runtime_name}.json",
            tmp_path / f"{runtime_name}.json",
        )

    target = tmp_path / f"{name}.json"
    payload = json.loads(target.read_text(encoding="utf-8"))
    mutate(payload["data"])
    payload["provenance"]["sha256_of_data"] = snapshots.data_checksum(payload["data"])
    target.write_text(json.dumps(payload), encoding="utf-8")

    try:
        with monkeypatch.context() as context:
            context.setattr(snapshots, "snapshot_dir", lambda: tmp_path)
            snapshots.clear_cache()
            with pytest.raises(snapshots.SnapshotError) as error:
                importlib.reload(lifecycle)
            return str(error.value)
    finally:
        snapshots.clear_cache()
        importlib.reload(lifecycle)


def test_dropped_life_table_age_fails_during_lifecycle_import(tmp_path, monkeypatch):
    """A checksum-consistent snapshot missing age 100 must not import."""

    def drop_age_100(data):
        del data["life_table"]["male"]["100"]

    message = _reload_lifecycle_against(
        tmp_path, monkeypatch, "cdc_life_table", drop_age_100
    )

    assert "cdc_life_table.json" in message
    assert "data.life_table.male ages are" in message
    assert "expected" in message


def test_extra_quality_weight_age_fails_during_lifecycle_import(tmp_path, monkeypatch):
    def insert_age_90(data):
        weights = data["quality_weights"]
        data["quality_weights"] = {
            age: weights[age] for age in ("25", "35", "45", "55", "65", "75", "85")
        }
        data["quality_weights"]["90"] = 0.77
        data["quality_weights"]["95"] = weights["95"]

    message = _reload_lifecycle_against(
        tmp_path, monkeypatch, "meps_quality_weights", insert_age_90
    )

    assert "meps_quality_weights.json" in message
    assert "data.quality_weights ages are" in message


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
