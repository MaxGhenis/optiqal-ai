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
    load_studies,
    normalize_doi,
    normalize_pmid,
)

EUROPE_PMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
FIXTURE_FIELDS = ("title", "journal", "year", "pmid", "doi", "resolved_at")


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

    result_pmid = _normalized_result_identifier(match, "pmid")
    result_doi = _normalized_result_identifier(match, "doi")
    raw_year = match.get("pubYear")
    year: int | str | None
    if isinstance(raw_year, str) and raw_year.isdigit():
        year = int(raw_year)
    elif isinstance(raw_year, (int, str)) and not isinstance(raw_year, bool):
        year = raw_year
    else:
        year = None
    return {
        "title": str(match.get("title") or "").strip(),
        "journal": str(match.get("journalTitle") or "").strip(),
        "year": year,
        "pmid": result_pmid,
        "doi": result_doi,
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


def refresh_fixture(studies_path: Path, fixture_path: Path) -> tuple[int, int]:
    identifiers = _table_identifiers(studies_path)
    fixture: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    for kind, identifier in identifiers:
        try:
            fixture[identifier] = _resolve_identifier(kind, identifier)
        except EvidenceValidationError as error:
            failures.append(str(error))
    if failures:
        failure_lines = "\n".join(f"- {failure}" for failure in failures)
        raise EvidenceValidationError(
            f"refusing to write an incomplete fixture; unresolved identifiers:\n{failure_lines}"
        )

    _atomic_write_fixture(fixture_path, fixture)
    rows = load_studies(studies_path, fixture_path)
    return len(rows), len(identifiers)


def check_fixture(studies_path: Path, fixture_path: Path) -> tuple[int, int]:
    """Check coverage using committed files only; this function never opens a URL."""
    rows = load_studies(studies_path, fixture_path)
    identifiers = {identifier for row in rows for identifier in row.identifiers}
    return len(rows), len(identifiers)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.refresh:
            row_count, identifier_count = refresh_fixture(
                args.studies_path, args.fixture_path
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
