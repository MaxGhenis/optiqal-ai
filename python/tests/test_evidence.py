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
    DEFAULT_CI_LEVEL,
    ENDPOINT_CLASSES,
    EvidenceValidationError,
    StudyEstimate,
    canonical_text,
    load_studies,
    normalize_doi,
    normalize_pmid,
    number_appears,
    text_digest,
)
from scripts import verify_evidence

PYTHON_ROOT = Path(__file__).resolve().parents[1]

EXAMPLE_ABSTRACT = (
    "<h4>Results</h4>Death occurred in 100 of 1000 participants "
    "(hazard ratio, 0.80; 95% CI, 0.70 to 0.90; P=0.01)."
)
EXAMPLE_QUOTE = (
    "Death occurred in 100 of 1000 participants "
    "(hazard ratio, 0.80; 95% CI, 0.70 to 0.90; P=0.01)."
)


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
        "notes": EXAMPLE_QUOTE,
    }
    row.update(overrides)
    return row


def _write_table(tmp_path: Path, rows: list[object]) -> Path:
    path = tmp_path / "studies.yaml"
    path.write_text(yaml.safe_dump(rows, sort_keys=False), encoding="utf-8")
    return path


def _write_fixture(
    tmp_path: Path,
    identifiers=("10.1000/example",),
    quotes=None,
) -> Path:
    path = tmp_path / "doi_fixture.json"
    row_quotes = (
        {"example2024": text_digest(EXAMPLE_QUOTE)} if quotes is None else quotes
    )
    fixture = {
        identifier: {
            "title": "Example trial",
            "journal": "Example Journal",
            "year": 2024,
            "pmid": None,
            "doi": identifier if "/" in identifier else None,
            "resolved_at": "2026-09-04",
            "abstract_sha256": text_digest(EXAMPLE_ABSTRACT),
            "quotes": dict(row_quotes),
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
    quote = "Blood pressure fell by -2.0 mm Hg (95% CI, -3.0 to -1.0)."
    table = _write_table(
        tmp_path,
        [
            _valid_row(
                doi=None,
                pmid=123456,
                estimate={"type": "MD", "value": -2.0, "ci_low": -3.0, "ci_high": -1.0},
                role="calibration",
                endpoint="resting_systolic_blood_pressure_mmhg",
                notes=quote,
            )
        ],
    )
    fixture = _write_fixture(
        tmp_path, ("123456",), quotes={"example2024": text_digest(quote)}
    )

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
                        "journalInfo": {"journal": {"title": "Example Journal"}},
                        "pubYear": "2024",
                        "abstractText": EXAMPLE_ABSTRACT,
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
    entry = written["10.1000/example"]
    assert set(entry) == set(verify_evidence.FIXTURE_FIELDS)
    assert entry["pmid"] == "123456"
    assert entry["year"] == 2024
    assert entry["journal"] == "Example Journal"
    assert entry["abstract_sha256"] == text_digest(EXAMPLE_ABSTRACT)
    assert entry["quotes"] == {"example2024": text_digest(EXAMPLE_QUOTE)}


def test_refresh_reads_the_journal_from_either_europe_pmc_shape():
    core_result = {"journalInfo": {"journal": {"title": "Core Journal"}}}
    assert verify_evidence._journal_title(core_result) == "Core Journal"
    assert verify_evidence._journal_title({"journalTitle": "Lite Journal"}) == (
        "Lite Journal"
    )
    assert verify_evidence._journal_title({}) == ""


def test_refresh_from_abstracts_cache_needs_no_network(tmp_path, monkeypatch):
    table = _write_table(tmp_path, [_valid_row()])
    fixture = _write_fixture(tmp_path, ())
    cache = tmp_path / "abstracts.json"
    cache.write_text(
        json.dumps(
            {
                "10.1000/example": {
                    "doi": "10.1000/example",
                    "pmid": "123456",
                    "title": "Example trial",
                    "journal": "Cached Journal",
                    "year": "2024",
                    "abstract": EXAMPLE_ABSTRACT,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        verify_evidence.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: pytest.fail("--abstracts-cache opened a URL"),
    )

    assert verify_evidence.refresh_fixture(
        table, fixture, abstracts_cache_path=cache
    ) == (1, 1)

    entry = json.loads(fixture.read_text(encoding="utf-8"))["10.1000/example"]
    assert entry["journal"] == "Cached Journal"
    assert entry["quotes"] == {"example2024": text_digest(EXAMPLE_QUOTE)}


def test_refresh_refuses_a_quote_absent_from_the_abstract(tmp_path):
    table = _write_table(
        tmp_path, [_valid_row(notes="An invented HR of 0.80 (0.70 to 0.90).")]
    )
    fixture = _write_fixture(tmp_path, ())
    cache = tmp_path / "abstracts.json"
    cache.write_text(
        json.dumps({"10.1000/example": {"abstract": EXAMPLE_ABSTRACT}}),
        encoding="utf-8",
    )

    with pytest.raises(
        EvidenceValidationError, match="not a substring of the abstract"
    ):
        verify_evidence.refresh_fixture(table, fixture, abstracts_cache_path=cache)

    assert not fixture.exists() or "10.1000/example" not in json.loads(
        fixture.read_text(encoding="utf-8")
    )


def test_check_rejects_an_abstracts_cache_argument(capsys):
    with pytest.raises(SystemExit):
        verify_evidence.main(["--check", "--abstracts-cache", "cache.json"])

    assert "only meaningful with --refresh" in capsys.readouterr().err


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


def test_confidence_level_defaults_and_is_bounded(tmp_path):
    assert _load_one(tmp_path, _valid_row()).estimate.ci_level == DEFAULT_CI_LEVEL

    row = _valid_row()
    row["estimate"] = {**row["estimate"], "ci_level": 0.99}
    assert _load_one(tmp_path, row).estimate.ci_level == 0.99

    for rejected in (0.5, 1.0, 95.0, -0.1):
        row = _valid_row()
        row["estimate"] = {**row["estimate"], "ci_level": rejected}
        table = _write_table(tmp_path, [row])
        with pytest.raises(EvidenceValidationError, match="estimate.ci_level"):
            load_studies(table, _write_fixture(tmp_path))


def test_rejects_an_unclassified_endpoint(tmp_path):
    table = _write_table(tmp_path, [_valid_row(endpoint="bone_mineral_density")])

    with pytest.raises(EvidenceValidationError, match="not classified"):
        load_studies(table, _write_fixture(tmp_path))


def test_every_committed_endpoint_is_classified():
    for row in load_studies():
        assert row.endpoint in ENDPOINT_CLASSES


def test_rejects_a_quote_missing_one_of_the_three_numbers(tmp_path):
    quote = "Death occurred in 100 of 1000 participants (hazard ratio, 0.80)."
    table = _write_table(tmp_path, [_valid_row(notes=quote)])
    fixture = _write_fixture(tmp_path, quotes={"example2024": text_digest(quote)})

    with pytest.raises(EvidenceValidationError, match="ci_low"):
        load_studies(table, fixture)


def test_rejects_a_quote_whose_digest_is_not_the_confirmed_one(tmp_path):
    table = _write_table(
        tmp_path,
        [_valid_row(notes="Deaths gave a hazard ratio of 0.80 (0.70 to 0.90).")],
    )

    with pytest.raises(EvidenceValidationError, match="does not match the abstract"):
        load_studies(table, _write_fixture(tmp_path))


def test_rejects_a_row_the_fixture_never_confirmed(tmp_path):
    table = _write_table(tmp_path, [_valid_row()])

    with pytest.raises(EvidenceValidationError, match="records no confirmed quote"):
        load_studies(table, _write_fixture(tmp_path, quotes={}))


def test_rejects_empty_notes(tmp_path):
    table = _write_table(tmp_path, [_valid_row(notes="   ")])

    with pytest.raises(EvidenceValidationError, match="verbatim abstract sentence"):
        load_studies(table, _write_fixture(tmp_path))


def test_number_matching_accepts_middle_dot_decimals_and_bare_points():
    assert number_appears("HR 0\u00b786, 95% CI 0\u00b781-0\u00b791", 0.86)
    assert number_appears("rate ratio, .62; CI .38-.99", 0.62)
    assert number_appears("difference -3.5 mm Hg [-4.6 to -2.3]", -3.5)
    assert not number_appears("HR 10.86 in 20.86 of them", 0.86)


def test_canonical_text_keeps_bare_comparison_operators():
    canonical = canonical_text("<h4>Results</h4>HR 0.68 (0.59 to 0.78, p<0.001).")
    assert canonical == "Results HR 0.68 (0.59 to 0.78, p<0.001)."


def test_every_committed_row_carries_its_verifier():
    for row in load_studies():
        assert row.extracted_by == "gpt-5.6-sol lane 2026-09-04"
        assert row.verified_by == (
            "claude-opus-5 review lane 2026-09-04; europepmc refresh 2026-09-04"
        )


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
