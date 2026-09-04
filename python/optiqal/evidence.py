"""Fail-closed loading for the study-level evidence table."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml

from optiqal.confounding import STUDY_QUALITY_SHRINKAGE

EstimateType = Literal["HR", "RR", "OR", "MD", "SMD"]
StudyRole = Literal[
    "direct",
    "mechanism",
    "transport",
    "harm",
    "baseline_risk",
    "calibration",
]

ESTIMATE_TYPES = frozenset({"HR", "RR", "OR", "MD", "SMD"})
STUDY_ROLES = frozenset(
    {"direct", "mechanism", "transport", "harm", "baseline_risk", "calibration"}
)
RATIO_ESTIMATE_TYPES = frozenset({"HR", "RR", "OR"})

DATA_DIRECTORY = Path(__file__).resolve().parent / "data" / "evidence"
DEFAULT_STUDIES_PATH = DATA_DIRECTORY / "studies.yaml"
DEFAULT_FIXTURE_PATH = DATA_DIRECTORY / "doi_fixture.json"

_DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_DOI_PREFIX_PATTERN = re.compile(
    r"^(?:doi\s*:\s*|https?://(?:dx\.)?doi\.org/)", re.IGNORECASE
)
_PUBMED_URL_PATTERN = re.compile(
    r"^https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?$", re.IGNORECASE
)


class EvidenceValidationError(ValueError):
    """Raised when the evidence table cannot be trusted."""


@dataclass(frozen=True)
class StudyEstimate:
    """One point estimate and its confidence interval."""

    type: EstimateType
    value: float
    ci_low: float
    ci_high: float


@dataclass(frozen=True)
class StudyRow:
    """A validated study estimate used by the canonical model."""

    id: str
    doi: str | None
    pmid: str | None
    design: str
    population: str
    exposure: str
    comparator: str
    endpoint: str
    estimate: StudyEstimate
    role: StudyRole
    extracted_by: str
    verified: date
    notes: str

    @property
    def identifiers(self) -> tuple[str, ...]:
        """Return every normalized external identifier carried by the row."""
        return tuple(identifier for identifier in (self.doi, self.pmid) if identifier)


def normalize_doi(value: object) -> str:
    """Normalize a DOI to its lowercase bare form."""
    if not isinstance(value, str):
        raise ValueError("DOI must be a string")
    normalized = _DOI_PREFIX_PATTERN.sub("", value.strip()).strip().lower()
    if not normalized or not _DOI_PATTERN.fullmatch(normalized):
        raise ValueError(f"invalid DOI {value!r}")
    return normalized


def normalize_pmid(value: object) -> str:
    """Normalize a PMID to an unprefixed decimal string."""
    if isinstance(value, bool):
        raise ValueError("PMID must be a positive integer or digit string")
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
        url_match = _PUBMED_URL_PATTERN.fullmatch(text)
        if url_match:
            text = url_match.group(1)
        elif text.lower().startswith("pmid:"):
            text = text.split(":", 1)[1].strip()
    else:
        raise ValueError("PMID must be a positive integer or digit string")
    if not text.isascii() or not text.isdigit() or int(text) <= 0:
        raise ValueError(f"invalid PMID {value!r}")
    return str(int(text))


def _row_error(row_id: str, message: str) -> EvidenceValidationError:
    return EvidenceValidationError(f"study row {row_id!r}: {message}")


def _required_string(raw: Mapping[str, Any], key: str, row_id: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _row_error(row_id, f"{key} must be a nonempty string")
    return value.strip()


def _finite_number(value: object, field: str, row_id: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _row_error(row_id, f"estimate.{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise _row_error(row_id, f"estimate.{field} must be a finite number")
    return number


def _verified_date(value: object, row_id: str) -> date:
    if isinstance(value, datetime):
        raise _row_error(
            row_id, "verified must be an ISO calendar date, not a datetime"
        )
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise _row_error(row_id, "verified must be an ISO calendar date") from error
    raise _row_error(row_id, "verified must be an ISO calendar date")


def _fixture_identifiers(path: Path) -> frozenset[str]:
    try:
        raw_fixture = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EvidenceValidationError(
            f"evidence fixture does not exist: {path}"
        ) from None
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceValidationError(
            f"cannot read evidence fixture {path}: {error}"
        ) from error
    if not isinstance(raw_fixture, dict):
        raise EvidenceValidationError(f"evidence fixture {path} must be a JSON object")

    normalized: set[str] = set()
    for identifier, metadata in raw_fixture.items():
        if not isinstance(identifier, str):
            raise EvidenceValidationError(
                f"evidence fixture {path} has a non-string identifier"
            )
        try:
            if "/" in identifier or identifier.lower().startswith(
                (
                    "doi:",
                    "http://doi.org/",
                    "https://doi.org/",
                    "http://dx.doi.org/",
                    "https://dx.doi.org/",
                )
            ):
                normalized_identifier = normalize_doi(identifier)
            else:
                normalized_identifier = normalize_pmid(identifier)
        except ValueError as error:
            raise EvidenceValidationError(
                f"evidence fixture {path} has invalid identifier {identifier!r}: {error}"
            ) from error
        if not isinstance(metadata, dict):
            raise EvidenceValidationError(
                f"evidence fixture entry {identifier!r} must be a JSON object"
            )
        if normalized_identifier in normalized:
            raise EvidenceValidationError(
                f"evidence fixture {path} has duplicate normalized identifier "
                f"{normalized_identifier!r}"
            )
        normalized.add(normalized_identifier)
    return frozenset(normalized)


def _parse_row(raw: object, index: int, fixture_ids: frozenset[str]) -> StudyRow:
    missing_id = f"<missing id at index {index}>"
    if not isinstance(raw, dict):
        raise _row_error(missing_id, "row must be a mapping")

    raw_id = raw.get("id")
    row_id = (
        raw_id.strip() if isinstance(raw_id, str) and raw_id.strip() else missing_id
    )
    if row_id == missing_id:
        raise _row_error(row_id, "id must be a nonempty string")

    allowed_keys = {
        "id",
        "doi",
        "pmid",
        "design",
        "population",
        "exposure",
        "comparator",
        "endpoint",
        "estimate",
        "role",
        "extracted_by",
        "verified",
        "notes",
    }
    extra_keys = set(raw) - allowed_keys
    if extra_keys:
        raise _row_error(row_id, f"unknown fields: {sorted(extra_keys)}")

    design = raw.get("design")
    if not isinstance(design, str) or design not in STUDY_QUALITY_SHRINKAGE:
        raise _row_error(
            row_id,
            f"design must be one of {sorted(STUDY_QUALITY_SHRINKAGE)}",
        )

    role = raw.get("role")
    if not isinstance(role, str) or role not in STUDY_ROLES:
        raise _row_error(row_id, f"role must be one of {sorted(STUDY_ROLES)}")

    raw_estimate = raw.get("estimate")
    if not isinstance(raw_estimate, dict):
        raise _row_error(row_id, "estimate must be a mapping")
    estimate_extra_keys = set(raw_estimate) - {"type", "value", "ci_low", "ci_high"}
    if estimate_extra_keys:
        raise _row_error(
            row_id, f"unknown estimate fields: {sorted(estimate_extra_keys)}"
        )
    estimate_type = raw_estimate.get("type")
    if not isinstance(estimate_type, str) or estimate_type not in ESTIMATE_TYPES:
        raise _row_error(
            row_id, f"estimate.type must be one of {sorted(ESTIMATE_TYPES)}"
        )
    value = _finite_number(raw_estimate.get("value"), "value", row_id)
    ci_low = _finite_number(raw_estimate.get("ci_low"), "ci_low", row_id)
    ci_high = _finite_number(raw_estimate.get("ci_high"), "ci_high", row_id)
    if estimate_type in RATIO_ESTIMATE_TYPES:
        if min(value, ci_low, ci_high) <= 0:
            raise _row_error(
                row_id,
                f"{estimate_type} value and confidence interval must be positive",
            )
        brackets = math.log(ci_low) <= math.log(value) <= math.log(ci_high)
    else:
        brackets = ci_low <= value <= ci_high
    if not brackets:
        scale = "log scale" if estimate_type in RATIO_ESTIMATE_TYPES else "linear scale"
        raise _row_error(
            row_id, f"confidence interval must bracket value on the {scale}"
        )

    doi: str | None = None
    pmid: str | None = None
    if raw.get("doi") is not None:
        try:
            doi = normalize_doi(raw["doi"])
        except ValueError as error:
            raise _row_error(row_id, str(error)) from error
    if raw.get("pmid") is not None:
        try:
            pmid = normalize_pmid(raw["pmid"])
        except ValueError as error:
            raise _row_error(row_id, str(error)) from error
    if doi is None and pmid is None:
        raise _row_error(row_id, "a DOI or PMID is required")
    for identifier in (doi, pmid):
        if identifier is not None and identifier not in fixture_ids:
            raise _row_error(
                row_id,
                f"identifier {identifier!r} is absent from the DOI fixture",
            )

    notes = raw.get("notes", "")
    if not isinstance(notes, str):
        raise _row_error(row_id, "notes must be a string")

    return StudyRow(
        id=row_id,
        doi=doi,
        pmid=pmid,
        design=design,
        population=_required_string(raw, "population", row_id),
        exposure=_required_string(raw, "exposure", row_id),
        comparator=_required_string(raw, "comparator", row_id),
        endpoint=_required_string(raw, "endpoint", row_id),
        estimate=StudyEstimate(
            type=estimate_type,
            value=value,
            ci_low=ci_low,
            ci_high=ci_high,
        ),
        role=role,
        extracted_by=_required_string(raw, "extracted_by", row_id),
        verified=_verified_date(raw.get("verified"), row_id),
        notes=notes,
    )


def load_studies(
    path: str | Path | None = None,
    fixture_path: str | Path | None = None,
) -> list[StudyRow]:
    """Load and validate the evidence table against the offline DOI fixture."""
    studies_path = Path(path) if path is not None else DEFAULT_STUDIES_PATH
    resolved_fixture_path = (
        Path(fixture_path) if fixture_path is not None else DEFAULT_FIXTURE_PATH
    )
    fixture_ids = _fixture_identifiers(resolved_fixture_path)
    try:
        raw_rows = yaml.safe_load(studies_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EvidenceValidationError(
            f"evidence table does not exist: {studies_path}"
        ) from None
    except (OSError, yaml.YAMLError) as error:
        raise EvidenceValidationError(
            f"cannot read evidence table {studies_path}: {error}"
        ) from error
    if not isinstance(raw_rows, list):
        raise EvidenceValidationError(
            f"evidence table {studies_path} must be a YAML list"
        )

    rows: list[StudyRow] = []
    seen_ids: set[str] = set()
    for index, raw_row in enumerate(raw_rows):
        row = _parse_row(raw_row, index, fixture_ids)
        if row.id in seen_ids:
            raise _row_error(row.id, "id is duplicated")
        seen_ids.add(row.id)
        rows.append(row)
    return rows
