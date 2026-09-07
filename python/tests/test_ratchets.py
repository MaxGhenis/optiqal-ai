"""Evidence-debt ratchets must only move downward deliberately."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
import yaml

from optiqal.confounding import ConfoundingPrior
from optiqal.evidence import StudyEstimate, StudyRow
from optiqal.lint import render_lint
from optiqal.ratchets import (
    DEFAULT_RATCHET_DIRECTORY,
    RATCHET_FILENAMES,
    RatchetEntry,
    find_typed_value_mismatches,
    generate_known_judgment_atoms,
    generate_known_unsourced_claims,
    generate_known_unverified_atoms,
    generate_ratchets,
    read_ratchet,
    write_ratchets,
)


def _study(
    study_id: str = "smith2020_trial",
    value: float = 0.8,
    role: str = "direct",
    endpoint: str = "all_cause_mortality",
) -> StudyRow:
    return StudyRow(
        id=study_id,
        doi="10.1000/example",
        pmid=None,
        design="rct_standard",
        population="100 adults",
        exposure="example treatment",
        comparator="placebo",
        endpoint=endpoint,
        estimate=StudyEstimate("HR", value, value - 0.1, value + 0.1),
        role=role,
        extracted_by="test suite",
        verified=date(2026, 9, 4),
        notes="",
    )


@pytest.fixture(scope="module")
def generated_ratchets():
    return generate_ratchets(since="2026-09-04")


@pytest.mark.parametrize("filename", RATCHET_FILENAMES)
def test_committed_ratchet_exactly_matches_live_debt(filename, generated_ratchets):
    snapshot_path = DEFAULT_RATCHET_DIRECTORY / filename
    committed_ids = {entry.id for entry in read_ratchet(snapshot_path)}
    generated_ids = {entry.id for entry in generated_ratchets[filename]}

    assert generated_ids == committed_ids, (
        f"{filename} has new debt {sorted(generated_ids - committed_ids)} and "
        f"fixed debt still in the snapshot {sorted(committed_ids - generated_ids)}"
    )


def test_unsourced_claim_requires_a_verified_link():
    catalog = {
        "linked": SimpleNamespace(
            hr_observed=0.8, qol_annual=0.0, study_ids=["smith2020_trial"]
        ),
        "dangling": SimpleNamespace(
            hr_observed=0.9, qol_annual=0.0, study_ids=["missing"]
        ),
        "qol": SimpleNamespace(hr_observed=1.0, qol_annual=0.01, study_ids=[]),
        "null": SimpleNamespace(hr_observed=1.0, qol_annual=0.0, study_ids=[]),
    }

    entries = generate_known_unsourced_claims(catalog, [_study()], since="2026-09-04")

    assert [entry.id for entry in entries] == ["dangling", "qol"]


def test_unsourced_claim_requires_an_endpoint_compatible_link():
    catalog = {
        "mace_only": SimpleNamespace(
            hr_observed=0.8, qol_annual=0.0, study_ids=["composite"]
        ),
        "mortality_row": SimpleNamespace(
            hr_observed=0.8, qol_annual=0.0, study_ids=["smith2020_trial"]
        ),
        "qol_claim_mortality_row": SimpleNamespace(
            hr_observed=1.0, qol_annual=0.01, study_ids=["smith2020_trial"]
        ),
        "qol_claim_qol_row": SimpleNamespace(
            hr_observed=1.0, qol_annual=0.01, study_ids=["sleep"]
        ),
        "calibration_only": SimpleNamespace(
            hr_observed=0.8, qol_annual=0.0, study_ids=["calibrator"]
        ),
        "both_legs": SimpleNamespace(
            hr_observed=0.8, qol_annual=0.01, study_ids=["smith2020_trial"]
        ),
    }
    studies = [
        _study(),
        _study("composite", endpoint="major_adverse_cardiovascular_event"),
        _study("sleep", endpoint="sleep_quality", role="transport"),
        _study("calibrator", role="calibration"),
    ]

    entries = generate_known_unsourced_claims(catalog, studies, since="2026-09-04")

    assert [entry.id for entry in entries] == [
        "both_legs",
        "calibration_only",
        "mace_only",
        "qol_claim_mortality_row",
    ]
    reasons = {entry.id: entry.reason for entry in entries}
    assert "a mortality effect" in reasons["mace_only"]
    assert "a quality-of-life effect" in reasons["qol_claim_mortality_row"]
    assert "a quality-of-life effect" in reasons["both_legs"]


def test_a_transport_link_still_answers_a_catalog_citation():
    from optiqal.ratchets import _catalog_unverified_reasons

    entry = SimpleNamespace(
        study_ids=["smith2020_trial"],
        sources=["Smith et al. 2020"],
        notes="",
        study_quality="rct_standard",
    )
    rows = {"smith2020_trial": _study(role="transport")}

    assert _catalog_unverified_reasons({"item": entry}, rows, {}) == {}


def test_unverified_generator_scans_raw_rows_catalog_and_yaml(tmp_path):
    studies_path = tmp_path / "studies.yaml"
    studies_path.write_text(
        yaml.safe_dump(
            [
                {
                    "id": "pending",
                    "doi": "10.1000/pending",
                }
            ]
        ),
        encoding="utf-8",
    )
    fixture_path = tmp_path / "doi_fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "10.1000/example": {
                    "title": "Smith trial",
                    "journal": "Journal",
                    "year": 2020,
                    "pmid": "123",
                    "doi": "10.1000/example",
                }
            }
        ),
        encoding="utf-8",
    )
    appendix_path = tmp_path / "appendix.md"
    appendix_path.write_text("# No calibration table\n", encoding="utf-8")
    references_path = tmp_path / "references.bib"
    references_path.write_text("% No calibration sources\n", encoding="utf-8")
    intervention_path = tmp_path / "intervention.yaml"
    intervention_path.write_text(
        yaml.safe_dump(
            {
                "id": "example",
                "lineage": {"study_ids": ["smith2020_trial"]},
                "evidence": {
                    "sources": [
                        {"citation": "Smith A et al. Trial. 2020", "year": 2020},
                        {"citation": "Jones B et al. Review. 2021", "year": 2021},
                    ]
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    catalog = {
        "cited": SimpleNamespace(
            study_ids=[],
            sources=["Smith et al. 2020"],
            notes="",
            study_quality=None,
        ),
        "target": SimpleNamespace(
            study_ids=[],
            sources=[],
            notes="",
            study_quality="rct_standard",
        ),
        "identified": SimpleNamespace(
            study_ids=[],
            sources=["https://pubmed.ncbi.nlm.nih.gov/123/"],
            notes="",
            study_quality=None,
        ),
        "crosswalk": SimpleNamespace(
            study_ids=["smith2020_trial"],
            sources=["https://pubmed.ncbi.nlm.nih.gov/123/"],
            notes="",
            study_quality=None,
        ),
        "publisher_suffix": SimpleNamespace(
            study_ids=[],
            sources=[
                "https://www.frontiersin.org/journals/nutrition/articles/"
                "10.3389/fnut.2024.1424972/full"
            ],
            notes="",
            study_quality=None,
        ),
    }

    entries = generate_known_unverified_atoms(
        catalog,
        [_study()],
        studies_path=studies_path,
        fixture_path=fixture_path,
        intervention_paths=[intervention_path],
        appendix_path=appendix_path,
        references_path=references_path,
        since="2026-09-04",
    )
    ids = {entry.id for entry in entries}

    assert ids == {
        "catalog:cited:citation",
        "catalog:identified:pmid:123",
        "catalog:publisher_suffix:doi:10.3389/fnut.2024.1424972",
        "catalog:target:target-tier",
        "yaml:example:citation:jones-2021",
        "study:pending",
    }


def test_judgment_generator_uses_category_fallback_and_emits_all_knobs():
    priors = {
        "exercise": ConfoundingPrior(2.0, 3.0),
        "other": ConfoundingPrior(1.0, 4.0),
    }
    catalog = {
        "category_match": SimpleNamespace(
            category="exercise",
            conf_alpha=2.0,
            conf_beta=3.0,
            hr_observed=1.0,
            study_ids=[],
        ),
        "fallback_match": SimpleNamespace(
            category="rx_current",
            conf_alpha=1.0,
            conf_beta=4.0,
            hr_observed=1.0,
            study_ids=[],
        ),
        "different": SimpleNamespace(
            category="rx_current",
            conf_alpha=2.0,
            conf_beta=4.0,
            hr_observed=0.9,
            study_ids=["smith2020_trial"],
        ),
    }

    entries = generate_known_judgment_atoms(
        catalog,
        [_study(value=0.8)],
        category_priors=priors,
        overlap_matrix={("a", "b"): 0.5},
        study_quality_shrinkage={"rct_standard": 0.2},
        evidence_effect_multipliers={"high": 1.0},
        since="2026-09-04",
    )
    by_id = {entry.id: entry.reason for entry in entries}

    assert set(by_id) == {
        "catalog:different:confounding_prior",
        "catalog:different:typed_value_differs",
        "overlap:a->b",
        "study_quality_shrinkage:rct_standard",
        "evidence_effect_multiplier:high",
    }
    assert (
        by_id["catalog:different:typed_value_differs"]
        == "typed value differs from study row"
    )


def test_typed_mismatch_keeps_cross_endpoint_transport_as_judgment():
    catalog = {
        "sauna": SimpleNamespace(
            hr_observed=1.0,
            study_ids=["sauna_sudden_cardiac_death"],
        )
    }
    transport = _study(
        study_id="sauna_sudden_cardiac_death",
        value=0.37,
        role="transport",
        endpoint="sudden_cardiac_death",
    )

    assert find_typed_value_mismatches(catalog, [transport]) == {"sauna": (transport,)}


def test_typed_mismatch_keeps_all_cause_transport_rows():
    catalog = {
        "glucosamine": SimpleNamespace(
            hr_observed=1.0,
            study_ids=["glucosamine_all_cause"],
        )
    }
    transport = _study(study_id="glucosamine_all_cause", value=0.85, role="transport")

    assert find_typed_value_mismatches(catalog, [transport]) == {
        "glucosamine": (transport,)
    }


def test_unverified_generator_tracks_appendix_and_prior_bibliography(tmp_path):
    studies_path = tmp_path / "studies.yaml"
    studies_path.write_text("[]\n", encoding="utf-8")
    fixture_path = tmp_path / "doi_fixture.json"
    fixture_path.write_text("{}\n", encoding="utf-8")
    appendix_path = tmp_path / "appendix.md"
    appendix_path.write_text(
        """### F.1 RCT vs Observational Comparison

| Intervention | RCT Effect | Observational Effect | Ratio |
|--------------|------------|---------------------|-------|
| Exercise → CVD | HR 0.86 | HR 0.70 | 0.48 |
| Diet → mortality | HR 0.91 | HR 0.79 | 0.67 |

### F.2 Next section
""",
        encoding="utf-8",
    )
    references_path = tmp_path / "references.bib"
    references_path.write_text(
        """% Confounding calibration sources
@book{angrist2010credibility,
  title={Mostly harmless econometrics},
  author={Angrist, Joshua D},
  year={2010}
}
@article{lundborg2016schooling,
  title={Health returns to schooling},
  author={Lundborg, Petter},
  year={2016}
}
% Next section
""",
        encoding="utf-8",
    )
    calibration_study = _study(
        study_id="angrist2010credibility_exercise", role="calibration"
    )

    entries = generate_known_unverified_atoms(
        {},
        [calibration_study],
        studies_path=studies_path,
        fixture_path=fixture_path,
        intervention_paths=[],
        appendix_path=appendix_path,
        references_path=references_path,
        since="2026-09-04",
    )

    assert {entry.id for entry in entries} == {
        "appendix:calibration:diet-mortality",
        "appendix:calibration:exercise-cvd",
        "reference:lundborg2016schooling",
    }


def test_appendix_hazard_atom_requires_exact_type_point_and_ci(tmp_path):
    studies_path = tmp_path / "studies.yaml"
    studies_path.write_text("[]\n", encoding="utf-8")
    fixture_path = tmp_path / "doi_fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "10.1000/example": {
                    "title": "Smith mortality trial",
                    "journal": "Journal",
                    "year": 2020,
                    "pmid": None,
                    "doi": "10.1000/example",
                }
            }
        ),
        encoding="utf-8",
    )
    appendix_path = tmp_path / "appendix.md"
    appendix_path.write_text(
        """## E. Hazard Ratio Database

| Risk Factor | Comparison | HR | 95% CI | Source |
|-------------|------------|-----|--------|--------|
| **Smoking** | | | | |
| Current vs never | | 0.80 | [0.70, 0.90] | Smith 2020 |
| Former vs never | | 0.80 | [0.71, 0.90] | Smith 2020 |

## F. Next section
""",
        encoding="utf-8",
    )
    references_path = tmp_path / "references.bib"
    references_path.write_text("", encoding="utf-8")

    entries = generate_known_unverified_atoms(
        {},
        [_study()],
        studies_path=studies_path,
        fixture_path=fixture_path,
        intervention_paths=[],
        appendix_path=appendix_path,
        references_path=references_path,
        since="2026-09-04",
    )

    assert [entry.id for entry in entries] == ["appendix:hazard:smoking-former"]


def test_write_preserves_since_and_removes_stale_ids(tmp_path):
    original = {
        filename: [RatchetEntry(f"{filename}:kept", "old reason", "2025-01-02")]
        for filename in RATCHET_FILENAMES
    }
    write_ratchets(original, tmp_path)
    for filename in RATCHET_FILENAMES:
        path = tmp_path / filename
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        raw.append(
            {
                "id": f"{filename}:stale",
                "reason": "fixed",
                "since": "2024-01-01",
            }
        )
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    replacement = {
        filename: [
            RatchetEntry(f"{filename}:kept", "new reason", "2026-09-04"),
            RatchetEntry(f"{filename}:new", "new debt", "2026-09-04"),
        ]
        for filename in RATCHET_FILENAMES
    }
    written = write_ratchets(replacement, tmp_path)

    for entries in written.values():
        assert [(entry.id.rsplit(":", 1)[-1], entry.since) for entry in entries] == [
            ("kept", "2025-01-02"),
            ("new", "2026-09-04"),
        ]


def test_lint_prints_sorted_items_then_exactly_three_counts():
    catalog = {
        "z": SimpleNamespace(hr_observed=0.9, study_ids=[]),
        "a": SimpleNamespace(hr_observed=1.0, study_ids=["study"]),
    }
    snapshots = {
        "known_unsourced_claims.yaml": [RatchetEntry("z", "unsourced", "2026-09-04")],
        "known_unverified_atoms.yaml": [
            RatchetEntry("catalog:z", "unverified", "2026-09-04")
        ],
        "known_judgment_atoms.yaml": [
            RatchetEntry("catalog:z:confounding_prior", "judgment", "2026-09-04")
        ],
    }

    lines = render_lint(catalog, snapshots)

    assert lines[:2] == [
        "a\thr_observed=1.0\tstudy_ids=[study]\tratchet_status=clear",
        "z\thr_observed=0.9\tstudy_ids=[]\tratchet_status=unsourced,unverified,judgment",
    ]
    assert lines[-3:] == [
        "known_unsourced_claims: 1",
        "known_unverified_atoms: 1",
        "known_judgment_atoms: 1",
    ]
    assert len(lines) == len(catalog) + 3


def test_ratchet_entry_serializes_as_exact_three_field_mapping():
    entry = RatchetEntry("atom", "reason", "2026-09-04")
    assert json.loads(json.dumps(entry.__dict__)) == {
        "id": "atom",
        "reason": "reason",
        "since": "2026-09-04",
    }
