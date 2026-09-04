#!/usr/bin/env python3
"""Refresh or check the offline Europe PMC evidence fixture."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import yaml

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from optiqal.evidence import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    DEFAULT_STUDIES_PATH,
    EvidenceValidationError,
    canonical_text,
    load_studies,
    normalize_doi,
    normalize_pmid,
    text_digest,
)

EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
FIXTURE_FIELDS = (
    "title",
    "journal",
    "year",
    "pmid",
    "doi",
    "resolved_at",
    "abstract_sha256",
    "quotes",
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--refresh",
        action="store_true",
        help="Resolve all table identifiers through Europe PMC and rewrite the fixture.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Validate the table against the committed fixture without network access.",
    )
    parser.add_argument(
        "--abstracts-cache",
        type=Path,
        default=None,
        help=(
            "Refresh from a local JSON abstract cache instead of the network. "
            "Each entry maps an identifier to at least {title, journal, year, "
            "abstract}."
        ),
    )
    parser.add_argument(
        "--studies-path",
        type=Path,
        default=DEFAULT_STUDIES_PATH,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help=argparse.SUPPRESS,
    )
    return parser


def _table_identifiers(path: Path) -> list[tuple[str, str]]:
    """Read normalized ``(kind, identifier)`` pairs without needing a fixture."""
    try:
        raw_rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EvidenceValidationError(
            f"evidence table does not exist: {path}"
        ) from None
    except (OSError, yaml.YAMLError) as error:
        raise EvidenceValidationError(
            f"cannot read evidence table {path}: {error}"
        ) from error
    if not isinstance(raw_rows, list):
        raise EvidenceValidationError(f"evidence table {path} must be a YAML list")

    identifiers: dict[str, str] = {}
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, dict):
            raise EvidenceValidationError(
                f"study row '<missing id at index {index}>': row must be a mapping"
            )
        raw_id = raw_row.get("id")
        row_id = (
            raw_id.strip()
            if isinstance(raw_id, str) and raw_id.strip()
            else f"<missing id at index {index}>"
        )
        row_identifiers: list[tuple[str, str]] = []
        if raw_row.get("doi") is not None:
            try:
                row_identifiers.append(("doi", normalize_doi(raw_row["doi"])))
            except ValueError as error:
                raise EvidenceValidationError(
                    f"study row {row_id!r}: {error}"
                ) from error
        if raw_row.get("pmid") is not None:
            try:
                row_identifiers.append(("pmid", normalize_pmid(raw_row["pmid"])))
            except ValueError as error:
                raise EvidenceValidationError(
                    f"study row {row_id!r}: {error}"
                ) from error
        if not row_identifiers:
            raise EvidenceValidationError(
                f"study row {row_id!r}: a DOI or PMID is required"
            )
        for kind, identifier in row_identifiers:
            previous_kind = identifiers.get(identifier)
            if previous_kind is not None and previous_kind != kind:
                raise EvidenceValidationError(
                    f"study row {row_id!r}: identifier {identifier!r} is ambiguous"
                )
            identifiers[identifier] = kind
    return sorted((kind, identifier) for identifier, kind in identifiers.items())


def _normalized_result_identifier(result: dict[str, Any], kind: str) -> str | None:
    raw_identifier = result.get("doi") if kind == "doi" else result.get("pmid")
    if raw_identifier is None and kind == "pmid" and result.get("source") == "MED":
        raw_identifier = result.get("id")
    if raw_identifier is None:
        return None
    try:
        return (
            normalize_doi(raw_identifier)
            if kind == "doi"
            else normalize_pmid(raw_identifier)
        )
    except ValueError:
        return None


def _journal_title(result: dict[str, Any]) -> str:
    """Return the journal title from either shape Europe PMC uses.

    A ``resultType=core`` search result carries the title at
    ``journalInfo.journal.title`` and has no top-level ``journalTitle``; the
    lighter result shapes carry ``journalTitle``.  Reading only the latter is
    what left every journal empty in the previously committed fixture.
    """
    journal_info = result.get("journalInfo")
    if isinstance(journal_info, dict):
        journal = journal_info.get("journal")
        if isinstance(journal, dict):
            for key in ("title", "medlineAbbreviation", "isoabbreviation"):
                value = journal.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    value = result.get("journalTitle")
    return value.strip() if isinstance(value, str) else ""


def _publication_year(raw_year: Any) -> int | str | None:
    if isinstance(raw_year, str) and raw_year.isdigit():
        return int(raw_year)
    if isinstance(raw_year, (int, str)) and not isinstance(raw_year, bool):
        return raw_year
    return None


def _resolve_identifier(
    kind: str,
    identifier: str,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    query_prefix = "DOI" if kind == "doi" else "EXT_ID"
    query = urllib.parse.urlencode(
        {
            "query": f"{query_prefix}:{identifier}",
            "format": "json",
            "resultType": "core",
        }
    )
    request = urllib.request.Request(
        f"{EUROPE_PMC_SEARCH_URL}?{query}",
        headers={"User-Agent": "optiqal-evidence-verifier/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
        json.JSONDecodeError,
    ) as error:
        raise EvidenceValidationError(
            f"Europe PMC request failed for {identifier}: {error}"
        ) from error

    results = payload.get("resultList", {}).get("result", [])
    if not isinstance(results, list):
        raise EvidenceValidationError(
            f"Europe PMC returned malformed results for {identifier}"
        )
    match = next(
        (
            result
            for result in results
            if isinstance(result, dict)
            and _normalized_result_identifier(result, kind) == identifier
        ),
        None,
    )
    if match is None:
        raise EvidenceValidationError(f"Europe PMC did not resolve {identifier}")

    return {
        "title": str(match.get("title") or "").strip(),
        "journal": _journal_title(match),
        "year": _publication_year(match.get("pubYear")),
        "pmid": _normalized_result_identifier(match, "pmid"),
        "doi": _normalized_result_identifier(match, "doi"),
        "abstract": str(match.get("abstractText") or ""),
        "resolved_at": date.today().isoformat(),
    }


def _load_abstracts_cache(path: Path) -> dict[str, dict[str, Any]]:
    """Read a local abstract cache keyed by DOI or PMID."""
    try:
        raw_cache = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise EvidenceValidationError(
            f"abstracts cache does not exist: {path}"
        ) from None
    except (OSError, json.JSONDecodeError) as error:
        raise EvidenceValidationError(
            f"cannot read abstracts cache {path}: {error}"
        ) from error
    if not isinstance(raw_cache, dict):
        raise EvidenceValidationError(f"abstracts cache {path} must be a JSON object")

    records: dict[str, dict[str, Any]] = {}
    for key, metadata in raw_cache.items():
        if not isinstance(key, str) or not isinstance(metadata, dict):
            raise EvidenceValidationError(
                f"abstracts cache {path} entry {key!r} must map to a JSON object"
            )
        aliases = [key, metadata.get("pmid"), metadata.get("doi")]
        for alias in aliases:
            if alias is None:
                continue
            try:
                normalized = (
                    normalize_doi(alias)
                    if isinstance(alias, str) and "/" in alias
                    else normalize_pmid(alias)
                )
            except ValueError:
                continue
            records[normalized] = metadata
    return records


def _cached_identifier(
    identifier: str, cache: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Build the same record ``_resolve_identifier`` builds, without network."""
    metadata = cache.get(identifier)
    if metadata is None:
        raise EvidenceValidationError(
            f"the abstracts cache has no entry for {identifier}"
        )
    abstract = metadata.get("abstract")
    if not isinstance(abstract, str) or not abstract.strip():
        raise EvidenceValidationError(
            f"the abstracts cache entry for {identifier} carries no abstract"
        )
    cached_doi = metadata.get("doi")
    cached_pmid = metadata.get("pmid")
    return {
        "title": str(metadata.get("title") or "").strip(),
        "journal": str(metadata.get("journal") or "").strip(),
        "year": _publication_year(metadata.get("year")),
        "pmid": None if cached_pmid is None else normalize_pmid(cached_pmid),
        "doi": None if cached_doi is None else normalize_doi(cached_doi),
        "abstract": abstract,
        "resolved_at": date.today().isoformat(),
    }


def _atomic_write_fixture(path: Path, fixture: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
            json.dump(fixture, temporary_file, indent=2, sort_keys=True)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _table_rows(path: Path) -> list[dict[str, Any]]:
    """Read the raw table rows that carry an id, a quote and an identifier."""
    raw_rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_rows, list):
        raise EvidenceValidationError(f"evidence table {path} must be a YAML list")
    return [row for row in raw_rows if isinstance(row, dict)]


def _row_identifiers(raw_row: dict[str, Any]) -> list[str]:
    identifiers: list[str] = []
    if raw_row.get("doi") is not None:
        identifiers.append(normalize_doi(raw_row["doi"]))
    if raw_row.get("pmid") is not None:
        identifiers.append(normalize_pmid(raw_row["pmid"]))
    return identifiers


def _confirm_quotes(
    rows: list[dict[str, Any]],
    identifier: str,
    abstract: str,
) -> tuple[dict[str, str], list[str]]:
    """Confirm every row quote is a substring of ``abstract``.

    Returns the ``{row id: sha256}`` map to store and the list of failures.
    The substring relation is established here, with the abstract in hand; the
    offline check re-establishes it by comparing digests against
    ``abstract_sha256``, so an edited quote or a changed abstract fails.
    """
    canonical_abstract = canonical_text(abstract)
    quotes: dict[str, str] = {}
    failures: list[str] = []
    for raw_row in rows:
        if identifier not in _row_identifiers(raw_row):
            continue
        row_id = str(raw_row.get("id") or "").strip()
        notes = raw_row.get("notes")
        if not isinstance(notes, str) or not notes.strip():
            failures.append(
                f"study row {row_id!r} has no quoted abstract sentence in notes"
            )
            continue
        quote = canonical_text(notes)
        if quote not in canonical_abstract:
            failures.append(
                f"study row {row_id!r}: the quoted sentence is not a substring of the "
                f"abstract for {identifier}"
            )
            continue
        quotes[row_id] = text_digest(notes)
    return quotes, failures


def refresh_fixture(
    studies_path: Path,
    fixture_path: Path,
    *,
    abstracts_cache_path: Path | None = None,
) -> tuple[int, int]:
    """Rewrite the fixture from Europe PMC, or from a local abstract cache."""
    identifiers = _table_identifiers(studies_path)
    rows = _table_rows(studies_path)
    cache = (
        None
        if abstracts_cache_path is None
        else _load_abstracts_cache(abstracts_cache_path)
    )
    fixture: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for kind, identifier in identifiers:
        try:
            record = (
                _resolve_identifier(kind, identifier)
                if cache is None
                else _cached_identifier(identifier, cache)
            )
        except EvidenceValidationError as error:
            failures.append(str(error))
            continue
        abstract = str(record.pop("abstract", ""))
        if not abstract.strip():
            failures.append(f"{identifier} resolved without an abstract")
            continue
        quotes, quote_failures = _confirm_quotes(rows, identifier, abstract)
        failures.extend(quote_failures)
        record["abstract_sha256"] = text_digest(abstract)
        record["quotes"] = quotes
        fixture[identifier] = record
    if failures:
        failure_lines = "\n".join(f"- {failure}" for failure in failures)
        raise EvidenceValidationError(
            f"refusing to write an incomplete fixture; unresolved identifiers:\n{failure_lines}"
        )

    _atomic_write_fixture(fixture_path, fixture)
    rows_loaded = load_studies(studies_path, fixture_path)
    return len(rows_loaded), len(identifiers)


def check_fixture(studies_path: Path, fixture_path: Path) -> tuple[int, int]:
    """Check coverage using committed files only; this function never opens a URL."""
    rows = load_studies(studies_path, fixture_path)
    identifiers = {identifier for row in rows for identifier in row.identifiers}
    return len(rows), len(identifiers)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.check and args.abstracts_cache is not None:
        parser.error("--abstracts-cache is only meaningful with --refresh")
    try:
        if args.refresh:
            row_count, identifier_count = refresh_fixture(
                args.studies_path,
                args.fixture_path,
                abstracts_cache_path=args.abstracts_cache,
            )
            print(
                f"Refreshed evidence fixture: {row_count} study rows, "
                f"{identifier_count} identifiers."
            )
        else:
            row_count, identifier_count = check_fixture(
                args.studies_path, args.fixture_path
            )
            print(
                f"Evidence check passed: {row_count} study rows, "
                f"{identifier_count} identifiers."
            )
    except EvidenceValidationError as error:
        print(f"Evidence verification failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
