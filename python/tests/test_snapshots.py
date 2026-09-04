"""Tests for provenance-stamped runtime data snapshots."""

import json

import pytest

from optiqal import snapshots


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
