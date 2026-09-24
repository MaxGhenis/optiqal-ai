"""Generate the evidence-debt ratchets from live repository data.

The YAML files under ``data/ratchets`` are snapshots, not inputs to the
generators.  Keeping generation separate from snapshot loading makes both
sides of the ratchet testable: a newly-created atom and a stale, fixed atom
are equally visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

from .catalog import CATALOG, EVIDENCE_EFFECT_MULTIPLIERS, CatalogEntry
from .combination import OVERLAP_MATRIX
from .confounding import CATEGORY_PRIORS, STUDY_QUALITY_SHRINKAGE
from .evidence import (
    DEFAULT_FIXTURE_PATH,
    DEFAULT_STUDIES_PATH,
    RATIO_ESTIMATE_TYPES,
    SUPPORTING_ROLES,
    EvidenceValidationError,
    StudyRow,
    load_studies,
    normalize_doi,
    normalize_pmid,
)
from .intervention import INTERVENTIONS_DIR

RATCHET_FILENAMES = (
    "known_unsourced_claims.yaml",
    "known_unverified_atoms.yaml",
    "known_judgment_atoms.yaml",
)

TARGET_STUDY_QUALITY_TIERS = frozenset(
    {
        "rct_preregistered_hard_endpoint",
        "meta_analysis_rcts",
        "rct_standard",
        "cohort_large",
    }
)

_DOI_IN_TEXT = re.compile(r"10\.\d{4,9}/[^\s\]}>,;]+", re.IGNORECASE)
_PMID_IN_TEXT = re.compile(r"\bPMID\s*:?\s*(\d+)\b", re.IGNORECASE)
_PUBMED_URL_IN_TEXT = re.compile(
    r"https?://pubmed\.ncbi\.nlm\.nih\.gov/(\d+)/?", re.IGNORECASE
)
_YEAR_IN_TEXT = re.compile(r"\b(?:19|20)\d{2}\b")
_AUTHOR_YEAR_IN_TEXT = re.compile(
    r"\b[A-Z][A-Za-z'\N{RIGHT SINGLE QUOTATION MARK}-]+"
    r"(?:\s+(?:et\s+al\.?|&\s*[A-Z][A-Za-z'\N{RIGHT SINGLE QUOTATION MARK}-]+))?"
    r"[,.;()\s]+(?:19|20)\d{2}\b"
)
_BIB_ENTRY = re.compile(
    r"@(?P<kind>[A-Za-z]+)\s*\{\s*(?P<key>[^,\s]+)\s*,(?P<body>.*?)\n\}",
    re.DOTALL,
)
_BIB_FIELD = re.compile(
    r"(?m)^\s*(?P<name>[A-Za-z]+)\s*=\s*\{(?P<value>.*?)\}\s*,?\s*$",
    re.DOTALL,
)


def _find_repository_root(start: Path | None = None) -> Path:
    """Find the checkout root without depending on the process cwd."""
    candidate = (start or Path(__file__)).resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for directory in (candidate, *candidate.parents):
        if (directory / "REBUILD.md").is_file() and (
            directory / "python" / "optiqal"
        ).is_dir():
            return directory
    raise RuntimeError(f"cannot find repository root above {candidate}")


REPOSITORY_ROOT = _find_repository_root()
DEFAULT_RATCHET_DIRECTORY = REPOSITORY_ROOT / "python" / "optiqal" / "data" / "ratchets"
DEFAULT_INTERVENTION_DIRECTORY = INTERVENTIONS_DIR
DEFAULT_APPENDIX_PATH = REPOSITORY_ROOT / "docs" / "appendix.md"
DEFAULT_REFERENCES_PATH = REPOSITORY_ROOT / "docs" / "references.bib"


@dataclass(frozen=True, order=True)
class RatchetEntry:
    """One stable item of visible evidence or judgment debt."""

    id: str
    reason: str
    since: str

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("ratchet id must be nonempty")
        if not self.reason.strip():
            raise ValueError(f"ratchet entry {self.id!r} has an empty reason")
        try:
            parsed = date.fromisoformat(self.since)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"ratchet entry {self.id!r} has an invalid since date"
            ) from error
        if parsed.isoformat() != self.since:
            raise ValueError(
                f"ratchet entry {self.id!r} since must be an ISO calendar date"
            )


def _iso_date(value: str | date | datetime | None = None) -> str:
    if value is None:
        return date.today().isoformat()
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, date):
        return value.isoformat()
    parsed = date.fromisoformat(value)
    return parsed.isoformat()


def _entries(
    reasons: Mapping[str, str], since: str | date | datetime | None
) -> list[RatchetEntry]:
    iso_since = _iso_date(since)
    return [
        RatchetEntry(id=entry_id, reason=reasons[entry_id], since=iso_since)
        for entry_id in sorted(reasons)
    ]


def _verified_studies(
    studies: Iterable[StudyRow] | None,
    *,
    studies_path: Path = DEFAULT_STUDIES_PATH,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
) -> list[StudyRow]:
    if studies is not None:
        return list(studies)
    try:
        return load_studies(studies_path, fixture_path)
    except EvidenceValidationError:
        # Fail closed.  The raw-table scanner below still makes unresolved
        # identifiers visible, while no invalid table row is treated as verified.
        return []


def _supporting_rows(
    entry: CatalogEntry, rows_by_id: Mapping[str, StudyRow]
) -> list[StudyRow]:
    """Return the linked rows whose role carries evidence into a claim."""
    return [
        rows_by_id[study_id]
        for study_id in entry.study_ids
        if study_id in rows_by_id and rows_by_id[study_id].role in SUPPORTING_ROLES
    ]


def generate_known_unsourced_claims(
    catalog: Mapping[str, CatalogEntry] | None = None,
    studies: Iterable[StudyRow] | None = None,
    *,
    since: str | date | datetime | None = None,
) -> list[RatchetEntry]:
    """List typed catalog effects with no endpoint-compatible study row.

    A linked row only discharges the leg it can speak to: a mortality hazard
    ratio needs a row on a mortality endpoint, and an annual QoL effect needs a
    row on a quality-of-life endpoint.  A composite cardiovascular endpoint
    discharges neither, so linking one no longer hides the debt.
    """
    live_catalog = CATALOG if catalog is None else catalog
    rows_by_id = {row.id: row for row in _verified_studies(studies)}
    reasons: dict[str, str] = {}
    for item_id, entry in live_catalog.items():
        supporting = _supporting_rows(entry, rows_by_id)
        endpoint_classes = {row.endpoint_class for row in supporting}
        missing: list[str] = []
        if entry.hr_observed != 1.0 and "mortality" not in endpoint_classes:
            missing.append("mortality")
        if entry.qol_annual != 0.0 and "quality_of_life" not in endpoint_classes:
            missing.append("quality-of-life")
        if missing:
            reasons[item_id] = (
                f"catalog entry claims a {' and '.join(missing)} effect with no "
                "linked direct or transport study row on a matching endpoint"
            )
    return _entries(reasons, since)


def _load_raw_yaml_list(path: Path) -> list[Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, yaml.YAMLError) as error:
        raise ValueError(f"cannot read YAML list {path}: {error}") from error
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a YAML list")
    return value


def _fixture_records(path: Path) -> dict[str, Mapping[str, Any]]:
    try:
        fixture = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read evidence fixture {path}: {error}") from error
    if not isinstance(fixture, dict):
        raise ValueError(f"evidence fixture {path} must be a JSON object")
    normalized: dict[str, Mapping[str, Any]] = {}
    for identifier, metadata in fixture.items():
        if not isinstance(identifier, str) or not isinstance(metadata, Mapping):
            continue
        try:
            normalized_identifier = (
                normalize_doi(identifier)
                if "/" in identifier
                else normalize_pmid(identifier)
            )
        except ValueError:
            continue
        normalized[normalized_identifier] = metadata
    return normalized


def _fixture_identifiers(path: Path) -> frozenset[str]:
    return frozenset(_fixture_records(path))


def _row_external_identifiers(
    row: StudyRow, fixture: Mapping[str, Mapping[str, Any]]
) -> frozenset[str]:
    identifiers = set(row.identifiers)
    for row_identifier in row.identifiers:
        metadata = fixture.get(row_identifier, {})
        for key, normalizer in (("doi", normalize_doi), ("pmid", normalize_pmid)):
            value = metadata.get(key)
            if value is None:
                continue
            try:
                identifiers.add(normalizer(value))
            except ValueError:
                continue
    return frozenset(identifiers)


def _citation_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        citation = value.get("citation")
        if isinstance(citation, str):
            return citation.strip()
        return " ".join(str(part) for part in value.values() if part is not None)
    return str(value).strip()


def _contains_catalog_citation(text: str) -> bool:
    return bool(
        _DOI_IN_TEXT.search(text)
        or _PMID_IN_TEXT.search(text)
        or _PUBMED_URL_IN_TEXT.search(text)
        or _AUTHOR_YEAR_IN_TEXT.search(text)
    )


def _ascii_alnum(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]+", "", ascii_value.lower())


def _slug_words(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def _citation_year_token(citation: str, declared_year: Any = None) -> str | None:
    range_match = re.search(r"\b((?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2})\b", citation)
    if range_match:
        return re.sub(r"\s+", "", range_match.group(1)).replace("–", "-")
    decade_match = re.search(r"\b((?:19|20)\d{2}s)\b", citation)
    if decade_match:
        return decade_match.group(1)
    year_match = _YEAR_IN_TEXT.search(str(declared_year))
    if year_match is None:
        year_match = _YEAR_IN_TEXT.search(citation)
    return year_match.group(0) if year_match else None


def _citation_author_year(citation: str, declared_year: Any = None) -> str | None:
    """Build a readable citation slug; it is an id, not a resolver."""
    year = _citation_year_token(citation, declared_year)
    parenthetical_author = re.search(
        r"\(([A-Z][A-Za-z'\N{RIGHT SINGLE QUOTATION MARK}-]+)(?:\s+et\s+al\.?)?\s+"
        r"((?:19|20)\d{2})\b",
        citation,
    )
    if parenthetical_author:
        return f"{_slug_words(parenthetical_author.group(1))}-{parenthetical_author.group(2)}"
    if year is None:
        return None

    leading = re.split(r"\bet\s+al\.?|,|\.", citation, maxsplit=1)[0].strip()
    if "&" in leading:
        authors: list[str] = []
        for side in leading.split("&")[:2]:
            tokens = re.findall(
                r"[A-Za-z][A-Za-z'\N{RIGHT SINGLE QUOTATION MARK}-]*", side
            )
            if tokens:
                authors.append(tokens[0])
        if authors:
            return f"{_slug_words('-'.join(authors))}-{year}"

    tokens = re.findall(r"[A-Za-z][A-Za-z'\N{RIGHT SINGLE QUOTATION MARK}-]*", leading)
    if not tokens:
        return None
    if tokens[0].lower() in {"van", "von", "de", "der", "la"}:
        surname = "".join(tokens[:3])
    elif tokens[0].lower() == "surgeon" and len(tokens) > 1:
        surname = "-".join(tokens[:2])
    else:
        surname = tokens[0]
    return f"{_slug_words(surname)}-{year}"


def _citation_identifier(citation: str, source: Mapping[str, Any]) -> str | None:
    for key, normalizer in (("doi", normalize_doi), ("pmid", normalize_pmid)):
        if source.get(key) is not None:
            try:
                return normalizer(source[key])
            except ValueError:
                return None
    doi_match = _DOI_IN_TEXT.search(citation)
    if doi_match:
        try:
            return normalize_doi(doi_match.group(0).rstrip("."))
        except ValueError:
            return None
    pmid_match = _PMID_IN_TEXT.search(citation)
    if pmid_match is None:
        pmid_match = _PUBMED_URL_IN_TEXT.search(citation)
    if pmid_match:
        return normalize_pmid(pmid_match.group(1))
    return None


def _citation_slug(citation: str, declared_year: Any = None) -> str:
    author_year = _citation_author_year(citation, declared_year)
    if author_year:
        return author_year
    readable = _slug_words(citation)
    if readable:
        if readable.startswith("multiple-rcts"):
            return "multiple-rcts"
        return "-".join(readable.split("-")[:4])
    return hashlib.sha256(citation.encode("utf-8")).hexdigest()[:12]


def _normalized_words(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return {
        word
        for word in re.findall(r"[a-z0-9]+", normalized.lower())
        if len(word) >= 4
        and word
        not in {
            "with",
            "from",
            "that",
            "this",
            "study",
            "trial",
            "analysis",
            "review",
            "meta",
            "effects",
            "effect",
        }
    }


def _fixture_metadata_for_row(
    row: StudyRow, fixture: Mapping[str, Mapping[str, Any]]
) -> Mapping[str, Any]:
    for identifier in row.identifiers:
        if identifier in fixture:
            return fixture[identifier]
    return {}


def _study_matches_citation(
    row: StudyRow,
    source: Mapping[str, Any],
    fixture: Mapping[str, Mapping[str, Any]],
) -> bool:
    citation = _citation_text(source)
    identifier = _citation_identifier(citation, source)
    if identifier is not None and identifier in _row_external_identifiers(row, fixture):
        return True
    slug = _citation_slug(citation, source.get("year"))
    slug_parts = slug.split("-")
    years = {part for part in slug_parts if re.fullmatch(r"(?:19|20)\d{2}", part)}
    surnames = [part for part in slug_parts if part not in years]
    row_id = _ascii_alnum(row.id)
    if any(
        _ascii_alnum(f"{surname}{year}") in row_id
        for surname in surnames
        for year in years
    ):
        return True
    named_source = _ascii_alnum("".join(surnames))
    if (
        named_source
        and named_source in row_id
        and any(year in row_id for year in years)
    ):
        return True

    metadata = _fixture_metadata_for_row(row, fixture)
    title = str(metadata.get("title") or "")
    title_words = _normalized_words(title)
    citation_words = _normalized_words(citation)
    if title_words and len(title_words & citation_words) / len(title_words) >= 0.75:
        return True

    metadata_year = str(metadata.get("year") or "")
    row_context = f"{row.id} {title} {metadata.get('journal', '')}"
    distinctive = {
        word
        for word in citation_words
        if word not in {"cohort", "mortality", "cardiovascular", "randomized"}
    }
    return bool(
        years
        and metadata_year in years
        and distinctive & _normalized_words(row_context)
    )


def _unresolved_raw_study_reasons(
    rows: Sequence[Any], fixture_ids: frozenset[str]
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            reasons[f"study:<row-{index}>"] = (
                "raw evidence-table row is not a mapping and cannot be resolved"
            )
            continue
        raw_id = raw.get("id")
        row_id = (
            raw_id.strip()
            if isinstance(raw_id, str) and raw_id.strip()
            else f"row-{index}"
        )
        identifiers: list[str] = []
        invalid: list[str] = []
        for key, normalizer in (("doi", normalize_doi), ("pmid", normalize_pmid)):
            value = raw.get(key)
            if value is None:
                continue
            try:
                identifiers.append(normalizer(value))
            except ValueError:
                invalid.append(f"invalid {key} {value!r}")
        missing = [
            identifier for identifier in identifiers if identifier not in fixture_ids
        ]
        if not identifiers and not invalid:
            invalid.append("no DOI or PMID")
        if invalid or missing:
            details = [*invalid]
            if missing:
                details.append("fixture lacks " + ", ".join(sorted(missing)))
            reasons[f"study:{row_id}"] = (
                "study row is awaiting identifier resolution: " + "; ".join(details)
            )
    return reasons


def _catalog_identifiers(text: str) -> tuple[str, ...]:
    identifiers: set[str] = set()
    for match in _DOI_IN_TEXT.finditer(text):
        try:
            candidate = match.group(0).rstrip(".")
            candidate = re.sub(
                r"/(?:full|abstract|pdf|epdf)$", "", candidate, flags=re.IGNORECASE
            )
            identifiers.add(normalize_doi(candidate))
        except ValueError:
            continue
    for pattern in (_PMID_IN_TEXT, _PUBMED_URL_IN_TEXT):
        for match in pattern.finditer(text):
            identifiers.add(normalize_pmid(match.group(1)))
    return tuple(sorted(identifiers))


def _catalog_unverified_reasons(
    catalog: Mapping[str, CatalogEntry],
    studies_by_id: Mapping[str, StudyRow],
    fixture: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for item_id, entry in catalog.items():
        linked_rows = [
            studies_by_id[study_id]
            for study_id in entry.study_ids
            if study_id in studies_by_id
        ]
        has_supporting_link = any(row.role in SUPPORTING_ROLES for row in linked_rows)
        source_text = " ".join(_citation_text(source) for source in entry.sources)
        citation_text = f"{source_text} {entry.notes}".strip()
        has_citation = _contains_catalog_citation(citation_text)
        target_tier = entry.study_quality in TARGET_STUDY_QUALITY_TIERS
        if not (has_citation or target_tier):
            continue
        identifiers = _catalog_identifiers(citation_text)
        emitted_identifier = False
        for identifier in identifiers:
            if any(
                identifier in _row_external_identifiers(row, fixture)
                for row in linked_rows
            ):
                continue
            kind = "doi" if "/" in identifier else "pmid"
            entry_id = f"catalog:{item_id}:{kind}:{identifier}"
            matching_rows = [
                row
                for row in studies_by_id.values()
                if identifier in _row_external_identifiers(row, fixture)
            ]
            if matching_rows:
                reason = (
                    "catalog citation has an abstract-supported but unlinked study row"
                )
            else:
                reason = "catalog citation has no abstract-supported study row"
            reasons[entry_id] = f"{reason}: {identifier}"
            emitted_identifier = True

        if target_tier and not has_supporting_link and not emitted_identifier:
            reasons[f"catalog:{item_id}:target-tier"] = (
                "target-tier catalog claim has no identifiable abstract-supported study row"
            )
        elif (
            has_citation
            and not identifiers
            and not has_supporting_link
            and not target_tier
        ):
            reasons[f"catalog:{item_id}:citation"] = (
                "catalog author-year citation has no linked abstract-supported study row"
            )
    return reasons


def _intervention_unverified_reasons(
    paths: Iterable[Path],
    studies_by_id: Mapping[str, StudyRow],
    fixture: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for path in sorted(paths):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ValueError(
                f"cannot read intervention YAML {path}: {error}"
            ) from error
        if not isinstance(raw, Mapping):
            raise ValueError(f"intervention YAML {path} must contain a mapping")
        intervention_id = str(raw.get("id") or path.stem)
        lineage = raw.get("lineage")
        lineage = lineage if isinstance(lineage, Mapping) else {}
        raw_study_ids = lineage.get("study_ids", [])
        study_ids = (
            [str(value) for value in raw_study_ids]
            if isinstance(raw_study_ids, list)
            else []
        )
        linked_rows = [
            studies_by_id[study_id]
            for study_id in study_ids
            if study_id in studies_by_id
        ]

        evidence = raw.get("evidence")
        evidence = evidence if isinstance(evidence, Mapping) else {}
        evidence_sources = evidence.get("sources", [])
        if not isinstance(evidence_sources, list):
            evidence_sources = []
        confounding = raw.get("confounding")
        confounding = confounding if isinstance(confounding, Mapping) else {}
        calibration_sources = confounding.get("calibration_sources", [])
        if not isinstance(calibration_sources, list):
            calibration_sources = []
        lineage_sources = lineage.get("studies", [])
        if not isinstance(lineage_sources, list):
            lineage_sources = []
        sources = [*evidence_sources, *calibration_sources, *lineage_sources]
        used_ids: set[str] = set()
        for index, raw_source in enumerate(sources):
            source = (
                raw_source
                if isinstance(raw_source, Mapping)
                else {"citation": raw_source}
            )
            citation = _citation_text(source)
            if any(
                _study_matches_citation(row, source, fixture) for row in linked_rows
            ):
                continue
            slug = _citation_slug(citation, source.get("year"))
            entry_id = f"yaml:{intervention_id}:citation:{slug}"
            if entry_id in used_ids:
                # Evidence and calibration blocks often cite the same paper in
                # different shorthand.  One author-year locus is one atom.
                continue
            used_ids.add(entry_id)
            reasons[entry_id] = (
                "YAML citation has no abstract-supported study row: "
                f"{citation or f'source {index + 1}'}"
            )
    return reasons


def _markdown_section(path: Path, heading: str) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    start = text.find(heading)
    if start < 0:
        return ""
    remainder = text[start + len(heading) :]
    level = len(heading) - len(heading.lstrip("#"))
    next_heading = re.search(rf"(?m)^#{{1,{level}}}\s+", remainder)
    return remainder[: next_heading.start()] if next_heading else remainder


def _appendix_calibration_rows(path: Path) -> list[tuple[str, str]]:
    section = _markdown_section(path, "### F.1 RCT vs Observational Comparison")
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or cells[0] in {"Intervention", "--------------"}:
            continue
        if set(cells[0]) <= {"-", ":"}:
            continue
        rows.append((cells[0], line.strip()))
    return rows


def _hazard_row_slug(category: str, label: str) -> str:
    category_slug = _slug_words(category.replace("*", ""))
    lowered = label.lower()
    if category_slug == "smoking":
        detail = "former" if lowered.startswith("former") else "current"
    elif category_slug == "bmi":
        detail = "severe" if lowered.startswith("severely") else "obese"
    elif category_slug == "exercise":
        detail = "half-guideline" if lowered.startswith("75-") else "guideline"
    elif category_slug == "blood-pressure":
        detail = "stage-2" if "stage 2" in lowered else "stage-1"
        category_slug = "bp"
    elif category_slug == "diet":
        detail = "mediterranean-high"
    elif category_slug == "alcohol":
        detail = "heavy"
    elif category_slug == "sleep":
        detail = "short"
    elif category_slug == "social":
        detail = "isolation"
    else:
        detail = _slug_words(label)
    return f"{category_slug}-{detail}"


def _appendix_hazard_rows(
    path: Path,
) -> list[tuple[str, str, float, float, float, str, str]]:
    section = _markdown_section(path, "## E. Hazard Ratio Database")
    category = "uncategorized"
    rows: list[tuple[str, str, float, float, float, str, str]] = []
    for line in section.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            continue
        if cells[0].startswith("**"):
            category = cells[0].strip("*")
            continue
        if cells[0] in {"Risk Factor", "-------------"} or set(cells[0]) <= {
            "-",
            ":",
        }:
            continue
        try:
            point = float(cells[2])
        except ValueError:
            continue
        ci_match = re.fullmatch(
            r"\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]",
            cells[3],
        )
        if ci_match is None:
            continue
        rows.append(
            (
                _hazard_row_slug(category, cells[0]),
                "HR",
                point,
                float(ci_match.group(1)),
                float(ci_match.group(2)),
                cells[4],
                line.strip(),
            )
        )
    return rows


def _appendix_hazard_reasons(
    path: Path,
    studies: Sequence[StudyRow],
    fixture: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for (
        slug,
        estimate_type,
        point,
        low,
        high,
        source,
        row_text,
    ) in _appendix_hazard_rows(path):
        source_mapping = {"citation": source}
        exact = any(
            _study_matches_citation(row, source_mapping, fixture)
            and row.estimate.type == estimate_type
            and math.isclose(row.estimate.value, point, rel_tol=0.0, abs_tol=1e-12)
            and math.isclose(row.estimate.ci_low, low, rel_tol=0.0, abs_tol=1e-12)
            and math.isclose(row.estimate.ci_high, high, rel_tol=0.0, abs_tol=1e-12)
            for row in studies
        )
        if not exact:
            reasons[f"appendix:hazard:{slug}"] = (
                "appendix estimate is not stated exactly in the cited abstract: "
                + row_text
            )
    return reasons


def _appendix_unverified_reasons(
    path: Path,
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for label, row_text in _appendix_calibration_rows(path):
        slug = _slug_words(label)
        reasons[f"appendix:calibration:{slug}"] = (
            "appendix paired RCT/observational calibration row is not wholly "
            f"traceable to exact abstract estimates: {row_text}"
        )
    return reasons


def _bib_fields(body: str) -> dict[str, str]:
    return {
        match.group("name").lower(): match.group("value").strip()
        for match in _BIB_FIELD.finditer(body)
    }


def _bibliography_entries(
    path: Path,
) -> list[tuple[str, str, dict[str, str]]]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    return [
        (
            match.group("kind").lower(),
            match.group("key").strip(),
            _bib_fields(match.group("body")),
        )
        for match in _BIB_ENTRY.finditer(text)
    ]


def _bibliography_entry_has_row(
    key: str,
    fields: Mapping[str, str],
    studies: Sequence[StudyRow],
    fixture: Mapping[str, Mapping[str, Any]],
) -> bool:
    normalized_key = _ascii_alnum(key)
    key_core_match = re.match(r"([a-z]+)(\d{4})", normalized_key)
    key_core = "".join(key_core_match.groups()) if key_core_match else normalized_key
    bib_title_words = _normalized_words(fields.get("title", ""))
    for row in studies:
        row_id = _ascii_alnum(row.id)
        if normalized_key in row_id or row_id in normalized_key:
            return True
        metadata = _fixture_metadata_for_row(row, fixture)
        row_title_words = _normalized_words(str(metadata.get("title") or ""))
        if not row_title_words or not bib_title_words:
            continue
        overlap = len(row_title_words & bib_title_words) / min(
            len(row_title_words), len(bib_title_words)
        )
        if overlap >= 0.8:
            return True
        if key_core in row_id and overlap >= 0.5:
            return True
    return False


def _bibliography_unverified_reasons(
    path: Path,
    studies: Sequence[StudyRow],
    fixture: Mapping[str, Mapping[str, Any]],
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for kind, key, fields in _bibliography_entries(path):
        if _bibliography_entry_has_row(key, fields, studies, fixture):
            continue
        title = fields.get("title", "untitled reference").replace("\n", " ")
        if kind in {"book", "misc"}:
            reason = "reference is not an extractable study estimate"
        else:
            reason = "bibliography reference has no abstract-supported study row"
        reasons[f"reference:{key}"] = f"{reason}: {title}"
    return reasons


def generate_known_unverified_atoms(
    catalog: Mapping[str, CatalogEntry] | None = None,
    studies: Iterable[StudyRow] | None = None,
    *,
    studies_path: str | Path = DEFAULT_STUDIES_PATH,
    fixture_path: str | Path = DEFAULT_FIXTURE_PATH,
    intervention_paths: Iterable[str | Path] | None = None,
    appendix_path: str | Path = DEFAULT_APPENDIX_PATH,
    references_path: str | Path = DEFAULT_REFERENCES_PATH,
    since: str | date | datetime | None = None,
) -> list[RatchetEntry]:
    """List citation atoms that have not reached verified study rows."""
    studies_path = Path(studies_path)
    fixture_path = Path(fixture_path)
    live_studies = _verified_studies(
        studies, studies_path=studies_path, fixture_path=fixture_path
    )
    studies_by_id = {row.id: row for row in live_studies}
    live_catalog = CATALOG if catalog is None else catalog
    paths = (
        sorted(DEFAULT_INTERVENTION_DIRECTORY.glob("*.yaml"))
        if intervention_paths is None
        else [Path(path) for path in intervention_paths]
    )

    reasons: dict[str, str] = {}
    reasons.update(
        _unresolved_raw_study_reasons(
            _load_raw_yaml_list(studies_path), _fixture_identifiers(fixture_path)
        )
    )
    fixture = _fixture_records(fixture_path)
    reasons.update(_catalog_unverified_reasons(live_catalog, studies_by_id, fixture))
    reasons.update(_intervention_unverified_reasons(paths, studies_by_id, fixture))
    reasons.update(_appendix_hazard_reasons(Path(appendix_path), live_studies, fixture))
    reasons.update(_appendix_unverified_reasons(Path(appendix_path)))
    reasons.update(
        _bibliography_unverified_reasons(Path(references_path), live_studies, fixture)
    )
    return _entries(reasons, since)


def find_typed_value_mismatches(
    catalog: Mapping[str, CatalogEntry] | None = None,
    studies: Iterable[StudyRow] | None = None,
) -> dict[str, tuple[StudyRow, ...]]:
    """Return linked ratio estimates differing from the typed HR by over 1%.

    A role or endpoint mismatch does not erase the judgment: if a catalog claim
    links a ratio row, PR G must explicitly adjudicate why its typed HR differs.
    Non-ratio estimates remain incomparable to a hazard ratio and are skipped.
    """
    live_catalog = CATALOG if catalog is None else catalog
    studies_by_id = {row.id: row for row in _verified_studies(studies)}
    mismatches: dict[str, tuple[StudyRow, ...]] = {}
    for item_id, entry in live_catalog.items():
        differing: list[StudyRow] = []
        for study_id in entry.study_ids:
            row = studies_by_id.get(study_id)
            if row is None or row.estimate.type not in RATIO_ESTIMATE_TYPES:
                continue
            typed = entry.hr_observed
            difference = (
                abs(row.estimate.value - typed)
                if typed == 0
                else abs(row.estimate.value / typed - 1.0)
            )
            if difference > 0.01:
                differing.append(row)
        if differing:
            mismatches[item_id] = tuple(differing)
    return mismatches


def generate_known_judgment_atoms(
    catalog: Mapping[str, CatalogEntry] | None = None,
    studies: Iterable[StudyRow] | None = None,
    *,
    category_priors: Mapping[str, Any] | None = None,
    overlap_matrix: Mapping[tuple[str, str], float] | None = None,
    study_quality_shrinkage: Mapping[str, float] | None = None,
    evidence_effect_multipliers: Mapping[str, float] | None = None,
    since: str | date | datetime | None = None,
) -> list[RatchetEntry]:
    """List every live hand-set prior, overlap, retention, and multiplier."""
    live_catalog = CATALOG if catalog is None else catalog
    priors = CATEGORY_PRIORS if category_priors is None else category_priors
    overlaps = OVERLAP_MATRIX if overlap_matrix is None else overlap_matrix
    shrinkage = (
        STUDY_QUALITY_SHRINKAGE
        if study_quality_shrinkage is None
        else study_quality_shrinkage
    )
    multipliers = (
        EVIDENCE_EFFECT_MULTIPLIERS
        if evidence_effect_multipliers is None
        else evidence_effect_multipliers
    )
    fallback_prior = priors["other"]

    reasons: dict[str, str] = {}
    for item_id, entry in live_catalog.items():
        prior = priors.get(entry.category, fallback_prior)
        if (entry.conf_alpha, entry.conf_beta) != (prior.alpha, prior.beta):
            reasons[f"catalog:{item_id}:confounding_prior"] = (
                "per-item (conf_alpha, conf_beta) "
                f"({entry.conf_alpha:g}, {entry.conf_beta:g}) differs from the "
                f"CATEGORY_PRIORS fallback ({prior.alpha:g}, {prior.beta:g})"
            )

    for (first, second), value in overlaps.items():
        reasons[f"overlap:{first}->{second}"] = (
            f"OVERLAP_MATRIX directed retention is hand-set to {value:g}"
        )
    for design, value in shrinkage.items():
        reasons[f"study_quality_shrinkage:{design}"] = (
            f"STUDY_QUALITY_SHRINKAGE retention is hand-set to {value:g}"
        )
    for quality, value in multipliers.items():
        reasons[f"evidence_effect_multiplier:{quality}"] = (
            f"EVIDENCE_EFFECT_MULTIPLIERS value is hand-set to {value:g}"
        )
    for item_id in find_typed_value_mismatches(live_catalog, studies):
        reasons[f"catalog:{item_id}:typed_value_differs"] = (
            "typed value differs from study row"
        )

    return _entries(reasons, since)


def generate_ratchets(
    *, since: str | date | datetime | None = None
) -> dict[str, list[RatchetEntry]]:
    """Generate all three ratchet snapshots from live repository state."""
    studies = _verified_studies(None)
    return {
        "known_unsourced_claims.yaml": generate_known_unsourced_claims(
            studies=studies, since=since
        ),
        "known_unverified_atoms.yaml": generate_known_unverified_atoms(
            studies=studies, since=since
        ),
        "known_judgment_atoms.yaml": generate_known_judgment_atoms(
            studies=studies, since=since
        ),
    }


def read_ratchet(path: str | Path) -> list[RatchetEntry]:
    """Read and validate one committed ratchet snapshot."""
    path = Path(path)
    raw_entries = _load_raw_yaml_list(path)
    entries: list[RatchetEntry] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, Mapping):
            raise ValueError(f"{path}: ratchet row {index} must be a mapping")
        missing = {"id", "reason", "since"} - set(raw)
        if missing:
            raise ValueError(
                f"{path}: ratchet row {index} is missing fields {sorted(missing)}"
            )
        extra = set(raw) - {"id", "reason", "since"}
        if extra:
            raise ValueError(
                f"{path}: ratchet row {index} has unknown fields {sorted(extra)}"
            )
        entry_id = raw.get("id")
        reason = raw.get("reason")
        if not isinstance(entry_id, str) or not isinstance(reason, str):
            raise ValueError(f"{path}: ratchet row {index} needs string id and reason")
        since = _iso_date(raw.get("since"))
        entry = RatchetEntry(id=entry_id, reason=reason, since=since)
        if entry.id in seen:
            raise ValueError(f"{path}: duplicate ratchet id {entry.id!r}")
        seen.add(entry.id)
        entries.append(entry)
    return sorted(entries)


def write_ratchets(
    snapshots: Mapping[str, Sequence[RatchetEntry]] | None = None,
    directory: str | Path = DEFAULT_RATCHET_DIRECTORY,
) -> dict[str, list[RatchetEntry]]:
    """Write sorted snapshots while preserving the first-seen date by id."""
    generated = generate_ratchets() if snapshots is None else snapshots
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, list[RatchetEntry]] = {}
    for filename in RATCHET_FILENAMES:
        path = directory / filename
        existing = (
            {entry.id: entry for entry in read_ratchet(path)} if path.exists() else {}
        )
        entries = [
            replace(entry, since=existing.get(entry.id, entry).since)
            for entry in generated[filename]
        ]
        entries.sort()
        payload = yaml.safe_dump(
            [asdict(entry) for entry in entries],
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )
        path.write_text(payload, encoding="utf-8")
        written[filename] = entries
    return written


def _print_counts(snapshots: Mapping[str, Sequence[RatchetEntry]]) -> None:
    for filename in RATCHET_FILENAMES:
        print(f"{filename.removesuffix('.yaml')}: {len(snapshots[filename])}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write", action="store_true", help="rewrite committed ratchet snapshots"
    )
    args = parser.parse_args(argv)
    snapshots = write_ratchets() if args.write else generate_ratchets()
    _print_counts(snapshots)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through ``python -m``
    raise SystemExit(main())
