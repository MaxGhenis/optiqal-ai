"""Build the runtime life table from NVSR 72-12 Tables 2 and 3.

Regenerate from ``python/`` with::

    python -m optiqal.data_build.cdc_life_table

The source is Arias, Xu, and Kochanek, *United States Life Tables, 2021*,
NVSR 72(12), Table 2 (males) and Table 3 (females). The committed source
artifact ``data/cdc/nvsr72-12_tables_2_3.txt`` is the verbatim
``pdftotext -layout`` output of the report's pages 16-19, which hold both
tables. This module parses every row of it, checks the published columns
against each other, and writes ``data/snapshots/cdc_life_table.json``:

- ages 0-99 carry the published ``qx`` unchanged;
- age 100 is CDC's open-ended "100 and older" row, whose published
  ``qx = 1.000000`` is the probability of eventually dying, not an annual
  rate. It becomes the constant annual rate ``1 - exp(-l100 / T100)``, the
  rate at which a constant hazard reproduces the published ``e100 = T100 /
  l100``.

The legacy anchors the runtime used before this table are kept as audit
evidence in ``cdc_life_table_2021_source_comparison.json``. Their published
column must equal this parse at all 44 anchors, which ties the 2026-09-04 hand
transcription to the machine extraction.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import NoReturn, Optional, Sequence

from optiqal.data_build._common import file_checksum, render_snapshot, write_snapshot
from optiqal.snapshots import SnapshotError, data_checksum, load_snapshot

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PACKAGE_ROOT / "data" / "cdc" / "nvsr72-12_tables_2_3.txt"
SNAPSHOT_PATH = PACKAGE_ROOT / "data" / "snapshots" / "cdc_life_table.json"
SNAPSHOT_NAME = "cdc_life_table"
COMPARISON_NAME = "cdc_life_table_2021_source_comparison"

# The report PDF the source text was extracted from, and the command used.
SOURCE_PDF_URL = "https://www.cdc.gov/nchs/data/nvsr/nvsr72/nvsr72-12.pdf"
SOURCE_PDF_SHA256 = "f8aa394521fce65bfa6aa7a31516ab8b5247d6c918810597be27881ea5ee5875"
SOURCE_PDF_PAGES = "16-19"
SOURCE_RETRIEVED = "2026-09-27"
EXTRACTION_COMMAND = (
    "pdftotext -layout -f 16 -l 19 nvsr72-12.pdf nvsr72-12_tables_2_3.txt "
    "(Poppler 26.09.0)"
)

# Independent pins. Editing the source text or the legacy evidence without
# updating these is drift, not a refresh.
EXPECTED_SOURCE_SHA256 = (
    "d46ec353e6003cda5ff50ccbec3ffc9f20d98b7203e53af7dfe47a827d0fcb61"
)
EXPECTED_COMPARISON_DATA_SHA256 = (
    "574890b25cfd151c6948c68aeb79c1b0a36ebaf6558f819d2061e5641c434954"
)

SEXES = ("male", "female")
TABLE_SEX = {"2": "male", "3": "female"}
OPEN_AGE = 100
EXPECTED_AGES = tuple(range(OPEN_AGE + 1))
# The legacy sparse anchors, kept only to validate the comparison evidence.
LEGACY_ANCHOR_AGES = (0, 1, *range(5, OPEN_AGE + 1, 5))
COLUMNS = ("qx", "lx", "dx", "Lx", "Tx", "ex")
RADIX = 100_000
QX_DECIMALS = 6

# Rounding bounds for the published identities. The table prints lx, dx, Lx,
# and Tx as integers, qx to six decimals, and ex to one, each rounded from
# unrounded values, so an identity between printed values holds only to the
# sum of the rounding errors involved:
#   l(x+1) = lx (1 - qx):  0.5 + 0.5 + 0.5e-6 * RADIX       = 1.05
#   dx = lx - l(x+1):      0.5 + 0.5 + 0.5                  -> 1 (integers)
#   dx = qx lx:            0.5 + 0.5 qx + 0.5e-6 * RADIX    < 1.05
#   Tx = Lx + T(x+1):      0.5 + 0.5 + 0.5                  -> 1 (integers)
#   ex = Tx / lx:          0.05 + (0.5 + 0.5 ex) / lx       < 0.06 at lx >= 600
SURVIVOR_TOLERANCE = 1.05
DEATHS_TOLERANCE = 1
DEATH_RATE_TOLERANCE = 1.05
PERSON_YEARS_TOLERANCE = 1
EXPECTATION_TOLERANCE = 0.06

_TABLE_RE = re.compile(
    r"^Table ([23])\. Life table for (males|females): United States, 2021"
)
_ROW_RE = re.compile(
    r"^(?:(?P<age>\d+)–(?P<next>\d+)|(?P<open>100) and older)[ .]*?"
    r"\s+(?P<qx>\d\.\d{6})\s+(?P<lx>[\d,]+)\s+(?P<dx>[\d,]+)"
    r"\s+(?P<Lx>[\d,]+)\s+(?P<Tx>[\d,]+)\s+(?P<ex>\d+\.\d)\s*$"
)
# A line that starts like a table row but does not parse is a layout change,
# not something to skip.
_ROW_START_RE = re.compile(r"^(?:\d+–\d+|100 and older)")


class LifeTableSourceError(ValueError):
    """The committed NVSR source text is incomplete or internally inconsistent."""


def _fail(path: Path, message: str) -> NoReturn:
    raise SnapshotError(f"{path}: {message}")


def _integer(text: str) -> int:
    return int(text.replace(",", ""))


def parse_source_text(text: str) -> dict[str, dict[int, dict[str, float]]]:
    """Parse every Table 2 and Table 3 row from ``pdftotext -layout`` output.

    Returns ``{sex: {age: {qx, lx, dx, Lx, Tx, ex}}}`` with ages 0-100, where
    100 is the open-ended "100 and older" row. Raises
    :class:`LifeTableSourceError` on a missing, duplicated, or unparseable row.
    """
    tables: dict[str, dict[int, dict[str, float]]] = {}
    sex: Optional[str] = None
    for number, line in enumerate(text.splitlines(), start=1):
        heading = _TABLE_RE.match(line)
        if heading:
            sex = TABLE_SEX[heading.group(1)]
            if heading.group(2) != f"{sex}s":
                raise LifeTableSourceError(f"line {number}: table/sex mismatch")
            tables.setdefault(sex, {})
            continue
        if not _ROW_START_RE.match(line):
            continue
        row = _ROW_RE.match(line)
        if row is None:
            raise LifeTableSourceError(f"line {number}: unparseable row {line!r}")
        if sex is None:
            raise LifeTableSourceError(f"line {number}: row before any table")
        if row.group("open"):
            age = OPEN_AGE
        else:
            age = int(row.group("age"))
            if int(row.group("next")) != age + 1:
                raise LifeTableSourceError(f"line {number}: not a single-year row")
        if age in tables[sex]:
            raise LifeTableSourceError(f"line {number}: duplicate {sex} age {age}")
        tables[sex][age] = {
            "qx": float(row.group("qx")),
            "lx": _integer(row.group("lx")),
            "dx": _integer(row.group("dx")),
            "Lx": _integer(row.group("Lx")),
            "Tx": _integer(row.group("Tx")),
            "ex": float(row.group("ex")),
        }
    if tuple(sorted(tables)) != tuple(sorted(SEXES)):
        raise LifeTableSourceError(f"found tables for {sorted(tables)}")
    for sex in SEXES:
        if tuple(sorted(tables[sex])) != EXPECTED_AGES:
            missing = sorted(set(EXPECTED_AGES) - set(tables[sex]))
            raise LifeTableSourceError(f"{sex} table is missing ages {missing}")
        tables[sex] = {age: tables[sex][age] for age in EXPECTED_AGES}
    return tables


def check_published_identities(tables: dict) -> None:
    """Hold every published column to the others, within rounding.

    A row shifted by one, or any cell off by more than the printed rounding
    allows, breaks at least one identity. An error inside rounding, such as a
    wrong last digit of qx, can pass here; the source-text checksum pin, not
    this check, guards against those.
    """
    for sex in SEXES:
        table = tables[sex]
        if table[0]["lx"] != RADIX:
            raise LifeTableSourceError(f"{sex} l0 is {table[0]['lx']}, not {RADIX}")
        for age in EXPECTED_AGES[:-1]:
            row, after = table[age], table[age + 1]
            where = f"{sex} age {age}"
            if not 0 < row["qx"] < 1:
                raise LifeTableSourceError(f"{where}: qx {row['qx']} not in (0, 1)")
            if abs(row["lx"] * (1 - row["qx"]) - after["lx"]) > SURVIVOR_TOLERANCE:
                raise LifeTableSourceError(f"{where}: l(x+1) != lx (1 - qx)")
            if abs(row["dx"] - (row["lx"] - after["lx"])) > DEATHS_TOLERANCE:
                raise LifeTableSourceError(f"{where}: dx != lx - l(x+1)")
            if abs(row["qx"] * row["lx"] - row["dx"]) > DEATH_RATE_TOLERANCE:
                raise LifeTableSourceError(f"{where}: dx != qx lx")
            if not after["lx"] <= row["Lx"] <= row["lx"]:
                raise LifeTableSourceError(f"{where}: Lx outside [l(x+1), lx]")
            if abs(row["Tx"] - (row["Lx"] + after["Tx"])) > PERSON_YEARS_TOLERANCE:
                raise LifeTableSourceError(f"{where}: Tx != Lx + T(x+1)")
        for age in EXPECTED_AGES:
            row = table[age]
            if abs(row["ex"] - row["Tx"] / row["lx"]) > EXPECTATION_TOLERANCE:
                raise LifeTableSourceError(f"{sex} age {age}: ex != Tx / lx")
        open_row = table[OPEN_AGE]
        if open_row["qx"] != 1.0 or open_row["dx"] != open_row["lx"]:
            raise LifeTableSourceError(f"{sex} open interval does not close the table")
        if open_row["Lx"] != open_row["Tx"]:
            raise LifeTableSourceError(f"{sex} open interval Lx != Tx")


def open_interval_annual_rate(open_row: dict) -> float:
    """The annual death probability of a constant hazard with mean ``e100``.

    CDC's open row reports ``T100 / l100`` years of remaining life. A constant
    hazard ``m`` has mean remaining life ``1 / m``, so ``m = l100 / T100`` and
    the probability of dying within one year is ``1 - exp(-m)``.
    """
    hazard = open_row["lx"] / open_row["Tx"]
    return round(1.0 - math.exp(-hazard), QX_DECIMALS)


def build_data(tables: dict) -> dict:
    """The runtime ``data`` block: published qx at 0-99, annual rate at 100."""
    life_table = {}
    for sex in SEXES:
        rates = {str(age): tables[sex][age]["qx"] for age in EXPECTED_AGES[:-1]}
        rates[str(OPEN_AGE)] = open_interval_annual_rate(tables[sex][OPEN_AGE])
        life_table[sex] = rates
    return {"life_table": life_table}


def build_provenance(source_path: Path = SOURCE_PATH) -> dict:
    return {
        "source": (
            "Arias, Xu, and Kochanek, United States Life Tables, 2021, "
            "National Vital Statistics Reports 72(12), NCHS"
        ),
        "url": SOURCE_PDF_URL,
        "table": (
            "Table 2 (males) and Table 3 (females), qx column; ages 0-99 as "
            "published, age 100 converted from the open-ended '100 and older' row"
        ),
        "retrieved": SOURCE_RETRIEVED,
        "generator": "python -m optiqal.data_build.cdc_life_table",
        "version": 1,
        "status": "generated from the committed NVSR 72-12 source text",
        "doi": "10.15620/cdc:132418",
        "source_artifact": "optiqal/data/cdc/nvsr72-12_tables_2_3.txt",
        "source_artifact_sha256": file_checksum(source_path),
        "source_pdf_sha256": SOURCE_PDF_SHA256,
        "source_pdf_pages": SOURCE_PDF_PAGES,
        "extraction": EXTRACTION_COMMAND,
        "open_interval": (
            "Age 100 is 1 - exp(-l100 / T100): the annual death probability of "
            "a constant hazard whose mean remaining life equals the published "
            "e100. The published qx = 1.000000 for '100 and older' is the "
            "probability of eventually dying, not an annual rate."
        ),
        "replaces": (
            "The legacy anchors from Optiqal commit 5e472e22, recorded with "
            "their published counterparts in "
            "optiqal/data/snapshots/cdc_life_table_2021_source_comparison.json."
        ),
    }


def load_source_tables(source_path: Path = SOURCE_PATH) -> dict:
    """Parse and verify the committed source text."""
    if file_checksum(source_path) != EXPECTED_SOURCE_SHA256:
        _fail(source_path, "source text does not match the pinned checksum")
    tables = parse_source_text(source_path.read_text(encoding="utf-8"))
    check_published_identities(tables)
    return tables


def validate_legacy_comparison(tables: dict) -> None:
    """Check the legacy evidence and tie its published column to the parse."""
    comparison = load_snapshot(COMPARISON_NAME)
    if data_checksum(comparison.data) != EXPECTED_COMPARISON_DATA_SHA256:
        _fail(comparison.path, "data does not match the pinned source comparison")

    rows = comparison.data.get("rows")
    if not isinstance(rows, dict) or set(rows) != set(SEXES):
        _fail(comparison.path, "data.rows must contain male and female tables")

    exact_matches = 0
    ratios = []
    for sex in SEXES:
        if not isinstance(rows[sex], dict):
            _fail(comparison.path, f"data.rows.{sex} is not an object")
        if tuple(int(age) for age in rows[sex]) != LEGACY_ANCHOR_AGES:
            _fail(comparison.path, f"data.rows.{sex} has unexpected anchor ages")
        for age in LEGACY_ANCHOR_AGES:
            row = rows[sex][str(age)]
            legacy_qx = row.get("snapshot_qx")
            published_qx = row.get("published_qx")
            for name, value in (
                ("snapshot_qx", legacy_qx),
                ("published_qx", published_qx),
            ):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    _fail(
                        comparison.path, f"data.rows.{sex}.{age}.{name} is not numeric"
                    )
            if published_qx != tables[sex][age]["qx"]:
                _fail(
                    comparison.path,
                    f"data.rows.{sex}.{age}.published_qx {published_qx} != "
                    f"NVSR 72-12 source {tables[sex][age]['qx']}",
                )
            expected_ratio = round(legacy_qx / published_qx, 12)
            expected = {
                "snapshot_qx": legacy_qx,
                "published_qx": published_qx,
                "delta_snapshot_minus_published": round(legacy_qx - published_qx, 6),
                "ratio_snapshot_to_published": expected_ratio,
            }
            if row != expected:
                _fail(comparison.path, f"data.rows.{sex}.{age} is inconsistent")
            exact_matches += legacy_qx == published_qx
            if age != OPEN_AGE:
                ratios.append((expected_ratio, sex, age))

    summary = comparison.data.get("summary")
    if not isinstance(summary, dict):
        _fail(comparison.path, "data.summary is not an object")
    if summary.get("matches_source") is not False:
        _fail(comparison.path, "data.summary must record the legacy mismatch")
    if summary.get("anchors_compared") != 44 or exact_matches != 0:
        _fail(comparison.path, "comparison must cover 44 anchors with no exact matches")
    if summary.get("exact_matches") != exact_matches:
        _fail(comparison.path, "data.summary.exact_matches is inconsistent")
    for label, expected_row in (
        ("minimum_ratio", min(ratios)),
        ("maximum_ratio", max(ratios)),
    ):
        summary_row = summary.get(label)
        if not isinstance(summary_row, dict):
            _fail(comparison.path, f"data.summary.{label} is not an object")
        if (
            summary_row.get("ratio"),
            summary_row.get("sex"),
            summary_row.get("age"),
        ) != expected_row:
            _fail(comparison.path, f"data.summary.{label} is inconsistent")


def render_life_table_snapshot(source_path: Path = SOURCE_PATH) -> str:
    """The exact bytes this generator commits for the runtime snapshot."""
    tables = load_source_tables(source_path)
    return render_snapshot(build_provenance(source_path), build_data(tables))


def write_life_table_snapshot(
    source_path: Path = SOURCE_PATH, output_path: Path = SNAPSHOT_PATH
) -> Path:
    tables = load_source_tables(source_path)
    validate_legacy_comparison(tables)
    return write_snapshot(
        output_path, build_provenance(source_path), build_data(tables)
    )


def check_life_table_snapshot(
    source_path: Path = SOURCE_PATH, output_path: Path = SNAPSHOT_PATH
) -> bool:
    """Report whether the committed snapshot is byte-identical to a rebuild."""
    expected = render_life_table_snapshot(source_path)
    try:
        actual = output_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return actual == expected


def validate_committed_artifacts() -> None:
    """Source text, legacy evidence, and runtime snapshot all check out."""
    tables = load_source_tables()
    validate_legacy_comparison(tables)
    snapshot = load_snapshot(SNAPSHOT_NAME)
    if snapshot.data != build_data(tables):
        _fail(snapshot.path, "runtime data differs from the NVSR 72-12 source")
    if not check_life_table_snapshot():
        _fail(snapshot.path, "committed bytes differ from a rebuild")


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Regenerate the runtime life table from the committed source, or check it."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the source and compare the snapshot with a rebuild; write nothing",
    )
    args = parser.parse_args(argv)

    if args.check:
        tables = load_source_tables()
        validate_legacy_comparison(tables)
        if check_life_table_snapshot():
            print(f"{SNAPSHOT_PATH} is byte-identical to a rebuild from NVSR 72-12.")
            return
        print(
            f"{SNAPSHOT_PATH} differs from a rebuild; run this module without --check.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    output_path = write_life_table_snapshot()
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
