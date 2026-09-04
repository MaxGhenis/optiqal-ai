"""Fail-closed loading for the study-level evidence table."""

from __future__ import annotations

import hashlib
import html
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

EndpointClass = Literal["mortality", "quality_of_life", "intermediate"]

ESTIMATE_TYPES = frozenset({"HR", "RR", "OR", "MD", "SMD"})
STUDY_ROLES = frozenset(
    {"direct", "mechanism", "transport", "harm", "baseline_risk", "calibration"}
)
RATIO_ESTIMATE_TYPES = frozenset({"HR", "RR", "OR"})

# Confidence levels outside this open interval are either a typo or a credible
# interval that does not belong in a frequentist confidence-level field.
CI_LEVEL_BOUNDS = (0.5, 1.0)
DEFAULT_CI_LEVEL = 0.95

# Every endpoint the table may carry, classified by which model leg it can
# discharge.  The map is exhaustive on purpose: an endpoint that is not listed
# fails the loader, so a new endpoint must be classified before it can be used.
# ``intermediate`` means the endpoint is neither a death count nor a
# quality-of-life scale, so it supports neither leg without a transport step.
ENDPOINT_CLASSES: Mapping[str, EndpointClass] = {
    "all_cause_mortality": "mortality",
    "coronary_heart_disease_mortality": "mortality",
    "sudden_cardiac_death": "mortality",
    "survival": "mortality",
    "anxiety_symptoms_at_eight_weeks": "quality_of_life",
    "pittsburgh_sleep_quality_index_improvement": "quality_of_life",
    "sleep_quality": "quality_of_life",
    "coronary_heart_disease": "intermediate",
    "intracerebral_hemorrhage": "intermediate",
    "major_adverse_cardiovascular_event": "intermediate",
    "major_cardiovascular_event": "intermediate",
    "major_vascular_event": "intermediate",
    "myocardial_infarction": "intermediate",
    "primary_cardiovascular_composite": "intermediate",
    "primary_melanoma_incidence": "intermediate",
    "resting_systolic_blood_pressure_mmhg": "intermediate",
    "squamous_cell_carcinoma_incidence": "intermediate",
    "stroke": "intermediate",
    "total_cardiovascular_event": "intermediate",
}
MORTALITY_ENDPOINTS = frozenset(
    endpoint
    for endpoint, endpoint_class in ENDPOINT_CLASSES.items()
    if endpoint_class == "mortality"
)
QUALITY_OF_LIFE_ENDPOINTS = frozenset(
    endpoint
    for endpoint, endpoint_class in ENDPOINT_CLASSES.items()
    if endpoint_class == "quality_of_life"
)

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
# Europe PMC abstracts arrive as HTML fragments: ``<h4>`` section headings and
# ``<sup>``/``<sub>`` runs, with bare ``<`` characters inside text such as
# ``p<0.001``.  Requiring a letter after the bracket keeps those bare
# comparisons intact while still removing every real tag.
_HTML_TAG_PATTERN = re.compile(r"</?[A-Za-z][^<>]*>")
_WHITESPACE_PATTERN = re.compile(r"\s+")
# Lancet-family journals typeset decimals with a middle dot and use several
# dash characters; normalizing them lets a quoted sentence keep its verbatim
# glyphs while the numeric check still recognizes the estimate.
_DECIMAL_TRANSLATION = str.maketrans(
    {"\u00b7": ".", "\u2013": "-", "\u2212": "-", "\u2014": "-"}
)


class EvidenceValidationError(ValueError):
    """Raised when the evidence table cannot be trusted."""


def canonical_text(value: str) -> str:
    """Return the comparison form of an abstract or a quoted sentence.

    HTML entities are decoded, real tags become a single space, and every run
    of whitespace collapses.  Abstracts and quotes go through the same function
    so that a quote taken from an abstract stays a substring of it.
    """
    unescaped = html.unescape(value)
    without_tags = _HTML_TAG_PATTERN.sub(" ", unescaped)
    return _WHITESPACE_PATTERN.sub(" ", without_tags).strip()


def text_digest(value: str) -> str:
    """Return the sha256 of the canonical form of ``value``."""
    return hashlib.sha256(canonical_text(value).encode("utf-8")).hexdigest()


def _number_renderings(value: float) -> set[str]:
    """Return every decimal rendering an abstract may use for ``value``."""
    renderings: set[str] = set()
    for text in (f"{value:g}", f"{value:.1f}", f"{value:.2f}", f"{value:.3f}"):
        if float(text) != value:
            continue
        renderings.add(text)
        if text.startswith("0."):
            renderings.add(text[1:])
        elif text.startswith("-0."):
            renderings.add("-" + text[2:])
    return renderings


def number_appears(text: str, value: float) -> bool:
    """Report whether ``value`` appears in ``text`` as a standalone number."""
    haystack = canonical_text(text).translate(_DECIMAL_TRANSLATION)
    for rendering in sorted(_number_renderings(value), key=len, reverse=True):
        pattern = r"(?<![\d.])" + re.escape(rendering) + r"(?![\d])"
        if re.search(pattern, haystack):
            return True
    return False


def endpoint_class(endpoint: str) -> EndpointClass | None:
    """Return which model leg ``endpoint`` can discharge, or ``None``."""
    return ENDPOINT_CLASSES.get(endpoint)


@dataclass(frozen=True)
class StudyEstimate:
    """One point estimate and its confidence interval."""

    type: EstimateType
    value: float
    ci_low: float
    ci_high: float
    ci_level: float = DEFAULT_CI_LEVEL


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
    verified_by: str | None = None

    @property
    def identifiers(self) -> tuple[str, ...]:
        """Return every normalized external identifier carried by the row."""
        return tuple(identifier for identifier in (self.doi, self.pmid) if identifier)

    @property
    def quote(self) -> str:
        """Return the verbatim abstract sentence this row was extracted from."""
        return canonical_text(self.notes)

    @property
    def quote_digest(self) -> str:
        """Return the sha256 the fixture records for this row's quote."""
        return text_digest(self.notes)

    @property
    def endpoint_class(self) -> EndpointClass | None:
        """Return which model leg this row's endpoint can discharge."""
        return endpoint_class(self.endpoint)


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


def _fixture_records(path: Path) -> dict[str, dict[str, Any]]:
    """Read the offline fixture keyed by normalized identifier."""
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

    records: dict[str, dict[str, Any]] = {}
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
        if normalized_identifier in records:
            raise EvidenceValidationError(
                f"evidence fixture {path} has duplicate normalized identifier "
                f"{normalized_identifier!r}"
            )
        records[normalized_identifier] = metadata
    return records


def _fixture_identifiers(path: Path) -> frozenset[str]:
    return frozenset(_fixture_records(path))


def _parse_row(
    raw: object, index: int, fixture: Mapping[str, Mapping[str, Any]]
) -> StudyRow:
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
        "verified_by",
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
    estimate_extra_keys = set(raw_estimate) - {
        "type",
        "value",
        "ci_low",
        "ci_high",
        "ci_level",
    }
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
    ci_level = (
        DEFAULT_CI_LEVEL
        if raw_estimate.get("ci_level") is None
        else _finite_number(raw_estimate.get("ci_level"), "ci_level", row_id)
    )
    lower_bound, upper_bound = CI_LEVEL_BOUNDS
    if not lower_bound < ci_level < upper_bound:
        raise _row_error(
            row_id,
            f"estimate.ci_level must be between {lower_bound:g} and {upper_bound:g}, "
            f"exclusive; got {ci_level:g}",
        )
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

    endpoint = _required_string(raw, "endpoint", row_id)
    if endpoint not in ENDPOINT_CLASSES:
        raise _row_error(
            row_id,
            f"endpoint {endpoint!r} is not classified in ENDPOINT_CLASSES; "
            "classify it as mortality, quality_of_life or intermediate first",
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
        if identifier is not None and identifier not in fixture:
            raise _row_error(
                row_id,
                f"identifier {identifier!r} is absent from the DOI fixture",
            )

    notes = raw.get("notes", "")
    if not isinstance(notes, str) or not notes.strip():
        raise _row_error(
            row_id,
            "notes must be the verbatim abstract sentence that states the estimate",
        )
    quote = canonical_text(notes)
    for field_name, number in (
        ("value", value),
        ("ci_low", ci_low),
        ("ci_high", ci_high),
    ):
        if not number_appears(quote, number):
            raise _row_error(
                row_id,
                f"estimate.{field_name} ({number:g}) does not appear as a number in "
                "the quoted abstract sentence",
            )
    digest = text_digest(notes)
    for identifier in (doi, pmid):
        if identifier is None:
            continue
        quotes = fixture[identifier].get("quotes")
        if not isinstance(quotes, dict) or row_id not in quotes:
            raise _row_error(
                row_id,
                f"the fixture entry for {identifier!r} records no confirmed quote for "
                "this row; rerun scripts/verify_evidence.py --refresh",
            )
        if quotes[row_id] != digest:
            raise _row_error(
                row_id,
                f"the quoted sentence does not match the abstract confirmed for "
                f"{identifier!r}; rerun scripts/verify_evidence.py --refresh",
            )

    return StudyRow(
        id=row_id,
        doi=doi,
        pmid=pmid,
        design=design,
        population=_required_string(raw, "population", row_id),
        exposure=_required_string(raw, "exposure", row_id),
        comparator=_required_string(raw, "comparator", row_id),
        endpoint=endpoint,
        estimate=StudyEstimate(
            type=estimate_type,
            value=value,
            ci_low=ci_low,
            ci_high=ci_high,
            ci_level=ci_level,
        ),
        role=role,
        extracted_by=_required_string(raw, "extracted_by", row_id),
        verified=_verified_date(raw.get("verified"), row_id),
        notes=quote,
        verified_by=(
            None
            if raw.get("verified_by") is None
            else _required_string(raw, "verified_by", row_id)
        ),
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
    fixture = _fixture_records(resolved_fixture_path)
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
        row = _parse_row(raw_row, index, fixture)
        if row.id in seen_ids:
            raise _row_error(row.id, "id is duplicated")
        seen_ids.add(row.id)
        rows.append(row)
    return rows
