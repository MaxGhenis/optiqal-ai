"""Tests for the fail-closed study evidence table."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

from optiqal.confounding import STUDY_QUALITY_SHRINKAGE
from optiqal.evidence import (
    EvidenceValidationError,
    StudyEstimate,
    load_studies,
    normalize_doi,
    normalize_pmid,
)
from scripts import verify_evidence

PYTHON_ROOT = Path(__file__).resolve().parents[1]


def _valid_row(**overrides):
    row = {
        "id": "example2024",
        "doi": "10.1000/example",
        "design": "rct_standard",
        "population": "100 adults",
        "exposure": "example intervention",
        "comparator": "placebo",
        "endpoint": "all_cause_mortality",
        "estimate": {"type": "HR", "value": 0.8, "ci_low": 0.7, "ci_high": 0.9},
        "role": "direct",
        "extracted_by": "test suite",
        "verified": "2026-09-04",
        "notes": "Abstract reports the estimate.",
    }
    row.update(overrides)
    return row


def _write_table(tmp_path: Path, rows: list[object]) -> Path:
    path = tmp_path / "studies.yaml"
    path.write_text(yaml.safe_dump(rows, sort_keys=False), encoding="utf-8")
    return path


def _write_fixture(tmp_path: Path, identifiers=("10.1000/example",)) -> Path:
    path = tmp_path / "doi_fixture.json"
    fixture = {
        identifier: {
            "title": "Example trial",
            "journal": "Example Journal",
            "year": 2024,
            "pmid": None,
            "doi": identifier if "/" in identifier else None,
            "resolved_at": "2026-09-04",
        }
        for identifier in identifiers
    }
    path.write_text(json.dumps(fixture), encoding="utf-8")
    return path


def _load_one(tmp_path: Path, row: dict):
    return load_studies(_write_table(tmp_path, [row]), _write_fixture(tmp_path))[0]


def test_loads_normalized_frozen_study_row(tmp_path):
    row = _load_one(
        tmp_path,
        _valid_row(doi="HTTPS://DOI.ORG/10.1000/EXAMPLE"),
    )

    assert row.id == "example2024"
    assert row.doi == "10.1000/example"
    assert row.identifiers == ("10.1000/example",)
    assert row.verified.isoformat() == "2026-09-04"
    assert row.estimate == StudyEstimate("HR", 0.8, 0.7, 0.9)
    with pytest.raises(FrozenInstanceError):
        row.estimate.value = 0.5


def test_loads_integer_pmid_and_linear_estimate(tmp_path):
    table = _write_table(
        tmp_path,
        [
            _valid_row(
                doi=None,
                pmid=123456,
                estimate={"type": "MD", "value": -2.0, "ci_low": -3.0, "ci_high": -1.0},
                role="calibration",
            )
        ],
    )
    fixture = _write_fixture(tmp_path, ("123456",))

    row = load_studies(table, fixture)[0]

    assert row.pmid == "123456"
    assert row.estimate.value == -2.0


@pytest.mark.parametrize("estimate_type", ["HR", "RR", "OR", "MD", "SMD"])
def test_accepts_every_estimate_type(tmp_path, estimate_type):
    row = _valid_row(
        estimate={"type": estimate_type, "value": 0.8, "ci_low": 0.7, "ci_high": 0.9}
    )
    assert _load_one(tmp_path, row).estimate.type == estimate_type


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"design": "case_series"}, "design must be one of"),
        ({"role": "heuristic"}, "role must be one of"),
        (
            {"estimate": {"type": "risk", "value": 0.8, "ci_low": 0.7, "ci_high": 0.9}},
            "estimate.type must be one of",
        ),
        (
            {
                "estimate": {
                    "type": "HR",
                    "value": float("nan"),
                    "ci_low": 0.7,
                    "ci_high": 0.9,
                }
            },
            "estimate.value must be a finite number",
        ),
        (
            {"estimate": {"type": "HR", "value": 0.8, "ci_low": 0.81, "ci_high": 0.9}},
            "confidence interval must bracket value on the log scale",
        ),
        (
            {"estimate": {"type": "OR", "value": 0.8, "ci_low": 0.0, "ci_high": 0.9}},
            "OR value and confidence interval must be positive",
        ),
        (
            {
                "estimate": {
                    "type": "SMD",
                    "value": -2.0,
                    "ci_low": -1.0,
                    "ci_high": 0.0,
                }
            },
            "confidence interval must bracket value on the linear scale",
        ),
        ({"doi": None}, "a DOI or PMID is required"),
        ({"verified": "September 4, 2026"}, "verified must be an ISO calendar date"),
    ],
)
def test_rejects_invalid_rows_with_row_id(tmp_path, change, message):
    table = _write_table(tmp_path, [_valid_row(**change)])
    fixture = _write_fixture(tmp_path)

    with pytest.raises(EvidenceValidationError) as error:
        load_studies(table, fixture)

    assert "example2024" in str(error.value)
    assert message in str(error.value)


def test_rejects_identifier_absent_from_fixture_with_row_id(tmp_path):
    table = _write_table(tmp_path, [_valid_row()])
    fixture = _write_fixture(tmp_path, ())

    with pytest.raises(EvidenceValidationError, match="example2024.*absent from"):
        load_studies(table, fixture)


def test_rejects_duplicate_ids(tmp_path):
    table = _write_table(tmp_path, [_valid_row(), _valid_row()])
    fixture = _write_fixture(tmp_path)

    with pytest.raises(EvidenceValidationError, match="example2024.*duplicated"):
        load_studies(table, fixture)


def test_rejects_non_list_document(tmp_path):
    table = tmp_path / "studies.yaml"
    table.write_text("id: not-a-list\n", encoding="utf-8")

    with pytest.raises(EvidenceValidationError, match="must be a YAML list"):
        load_studies(table, _write_fixture(tmp_path))


def test_identifier_normalization():
    assert normalize_doi(" DOI: 10.1000/ABC ") == "10.1000/abc"
    assert normalize_pmid("PMID: 00123") == "123"
    assert normalize_pmid("https://pubmed.ncbi.nlm.nih.gov/123/") == "123"
    with pytest.raises(ValueError):
        normalize_doi("not a DOI")
    with pytest.raises(ValueError):
        normalize_pmid(True)


def test_new_design_tiers_copy_the_closest_retention_values():
    assert STUDY_QUALITY_SHRINKAGE["cohort_meta_analysis"] == 0.30
    assert STUDY_QUALITY_SHRINKAGE["mendelian_randomization"] == 0.20


def test_check_is_offline(tmp_path, monkeypatch):
    table = _write_table(tmp_path, [_valid_row()])
    fixture = _write_fixture(tmp_path)
    monkeypatch.setattr(
        verify_evidence.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("--check attempted network access"),
    )

    assert verify_evidence.check_fixture(table, fixture) == (1, 1)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_refresh_resolves_identifier_and_atomically_rewrites_fixture(
    tmp_path, monkeypatch
):
    table = _write_table(tmp_path, [_valid_row()])
    fixture = _write_fixture(tmp_path, ())
    requested_queries = []

    def fake_urlopen(request, timeout):
        assert timeout == 30.0
        requested_queries.append(parse_qs(urlparse(request.full_url).query)["query"][0])
        payload = {
            "resultList": {
                "result": [
                    {
                        "doi": "10.1000/EXAMPLE",
                        "pmid": "123456",
                        "title": "Example trial",
                        "journalTitle": "Example Journal",
                        "pubYear": "2024",
                    }
                ]
            }
        }
        return _FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr(verify_evidence.urllib.request, "urlopen", fake_urlopen)

    assert verify_evidence.refresh_fixture(table, fixture) == (1, 1)
    assert requested_queries == ["DOI:10.1000/example"]
    written = json.loads(fixture.read_text(encoding="utf-8"))
    assert set(written) == {"10.1000/example"}
    assert set(written["10.1000/example"]) == set(verify_evidence.FIXTURE_FIELDS)
    assert written["10.1000/example"]["pmid"] == "123456"
    assert written["10.1000/example"]["year"] == 2024


def test_refresh_refuses_partial_fixture_on_unresolved_identifier(
    tmp_path, monkeypatch
):
    table = _write_table(tmp_path, [_valid_row()])
    fixture = tmp_path / "doi_fixture.json"
    original = '{"keep": "the old fixture"}\n'
    fixture.write_text(original, encoding="utf-8")
    payload = {"resultList": {"result": []}}
    monkeypatch.setattr(
        verify_evidence.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: _FakeResponse(json.dumps(payload).encode()),
    )

    with pytest.raises(EvidenceValidationError, match="refusing to write"):
        verify_evidence.refresh_fixture(table, fixture)

    assert fixture.read_text(encoding="utf-8") == original


def test_committed_evidence_fixture_passes_cli_check():
    result = subprocess.run(
        [sys.executable, "scripts/verify_evidence.py", "--check"],
        cwd=PYTHON_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Evidence check passed:" in result.stdout
