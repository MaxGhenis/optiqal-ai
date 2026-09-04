"""Fail-closed loader for the committed data snapshots.

Every table the engine treats as data — the life table, the cause-of-death
fractions, the MEPS quality weights — lives in a provenance-stamped JSON file
under ``optiqal/data/snapshots/`` and is loaded through this module. Nothing in
the engine may hold such a table as a literal: a literal drifts silently from
the artifact that produced it, which is what
``docs/DATA_PROVENANCE.md`` recorded as the transcription gap.

A snapshot file is::

    {"provenance": {"source": ..., "url": ..., "table": ..., "retrieved": ...,
                    "generator": ..., "version": 1, "sha256_of_data": ...},
     "data": {...}}

Loading fails closed. A missing file, unparseable JSON, a missing or blank
provenance key, a checksum that does not match the ``data`` block, a value that
is not a finite non-negative number, or an age table whose ages are not strictly
increasing all raise :class:`SnapshotError` naming the file. Because
``optiqal.lifecycle`` loads its snapshots at import, every one of those failures
surfaces at import rather than as a wrong number in a card.

The generators that write these files are in ``optiqal.data_build``; each
snapshot names its own regenerate command in ``provenance.generator``.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, Optional

SNAPSHOT_FORMAT_VERSION = 1

# Every snapshot must carry all of these, non-blank. ``sha256_of_data`` is
# checked separately because it is validated against the data itself.
REQUIRED_PROVENANCE_KEYS = (
    "source",
    "url",
    "table",
    "retrieved",
    "generator",
    "version",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class SnapshotError(RuntimeError):
    """A snapshot is missing, malformed, or fails a sanity check."""


def snapshot_dir() -> Path:
    """Directory holding the committed snapshots.

    Indirected through a function so tests can monkeypatch it at
    ``optiqal.snapshots.snapshot_dir`` and point the loader at a temporary file.
    """
    return Path(__file__).parent / "data" / "snapshots"


def canonical_json(data: Any) -> str:
    """Serialize ``data`` the one way the checksum is defined over."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def data_checksum(data: Any) -> str:
    """sha256 of the canonical serialization of a snapshot's ``data`` block."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    """A loaded, validated snapshot.

    The accessors do the shape checking a caller would otherwise skip: they
    raise rather than return a table with a hole in it.
    """

    name: str
    path: Path
    provenance: dict
    data: dict

    def fail(self, message: str) -> NoReturn:
        raise SnapshotError(f"{self.path}: {message}")

    def _node(self, path: tuple[str, ...]) -> Any:
        node: Any = self.data
        for i, key in enumerate(path):
            if not isinstance(node, dict):
                self.fail(f"data.{'.'.join(path[:i])} is not an object")
            if key not in node:
                self.fail(f"missing data.{'.'.join(path[: i + 1])}")
            node = node[key]
        return node

    def _number(self, node: Any, where: str, maximum: Optional[float]) -> float:
        if isinstance(node, bool) or not isinstance(node, (int, float)):
            self.fail(f"{where} is not a number: {node!r}")
        value = float(node)
        if not math.isfinite(value):
            self.fail(f"{where} is not finite: {value!r}")
        if value < 0:
            self.fail(f"{where} is negative: {value!r}")
        if maximum is not None and value > maximum:
            self.fail(f"{where} exceeds {maximum}: {value!r}")
        return value

    def value(self, *path: str, maximum: Optional[float] = None) -> float:
        """A single non-negative finite number."""
        where = f"data.{'.'.join(path)}"
        return self._number(self._node(path), where, maximum)

    def named_table(
        self, *path: str, keys: tuple[str, ...] = (), maximum: Optional[float] = None
    ) -> dict[str, float]:
        """A string-keyed table of numbers, e.g. condition -> decrement."""
        where = f"data.{'.'.join(path)}"
        node = self._node(path)
        if not isinstance(node, dict) or not node:
            self.fail(f"{where} is not a non-empty object")
        if keys and tuple(node) != keys:
            self.fail(f"{where} keys are {tuple(node)}, expected {keys}")
        return {k: self._number(v, f"{where}.{k}", maximum) for k, v in node.items()}

    def _age_keys(self, node: Any, where: str) -> list[int]:
        if not isinstance(node, dict) or not node:
            self.fail(f"{where} is not a non-empty object")
        ages: list[int] = []
        for key in node:
            if not isinstance(key, str) or not re.fullmatch(r"-?\d+", key):
                self.fail(f"{where} has a non-integer age key: {key!r}")
            ages.append(int(key))
        if any(b <= a for a, b in zip(ages, ages[1:])):
            self.fail(f"{where} ages are not strictly increasing: {ages}")
        if ages[0] < 0:
            self.fail(f"{where} has a negative age: {ages[0]}")
        return ages

    def age_table(self, *path: str, maximum: Optional[float] = None) -> dict[int, float]:
        """An age -> number table, keyed by int, ages strictly increasing."""
        where = f"data.{'.'.join(path)}"
        node = self._node(path)
        ages = self._age_keys(node, where)
        return {
            age: self._number(node[str(age)], f"{where}.{age}", maximum) for age in ages
        }

    def age_rows(
        self,
        *path: str,
        columns: tuple[str, ...],
        sums_to: Optional[float] = None,
        tolerance: float = 1e-9,
    ) -> dict[int, dict[str, float]]:
        """An age -> {column: number} table, e.g. the cause fractions."""
        where = f"data.{'.'.join(path)}"
        node = self._node(path)
        ages = self._age_keys(node, where)
        rows: dict[int, dict[str, float]] = {}
        for age in ages:
            row = node[str(age)]
            row_where = f"{where}.{age}"
            if not isinstance(row, dict):
                self.fail(f"{row_where} is not an object")
            if tuple(row) != columns:
                self.fail(f"{row_where} keys are {tuple(row)}, expected {columns}")
            values = {
                c: self._number(row[c], f"{row_where}.{c}", maximum=None)
                for c in columns
            }
            if sums_to is not None and abs(sum(values.values()) - sums_to) > tolerance:
                self.fail(f"{row_where} sums to {sum(values.values())!r}, not {sums_to}")
            rows[age] = values
        return rows


_CACHE: dict[Path, Snapshot] = {}


def clear_cache() -> None:
    """Drop the loaded-snapshot cache (tests that swap the directory)."""
    _CACHE.clear()


def load_snapshot(name: str) -> Snapshot:
    """Load and validate ``<snapshot_dir>/<name>.json``.

    Raises :class:`SnapshotError`, naming the file, on anything unexpected.
    """
    path = snapshot_dir() / f"{name}.json"
    cached = _CACHE.get(path)
    if cached is not None:
        return cached

    if not path.exists():
        raise SnapshotError(f"{path}: snapshot file is missing")
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"{path}: cannot be read as JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise SnapshotError(f"{path}: top level is not an object")
    provenance = raw.get("provenance")
    if not isinstance(provenance, dict) or not provenance:
        raise SnapshotError(f"{path}: missing provenance block")
    data = raw.get("data")
    if not isinstance(data, dict) or not data:
        raise SnapshotError(f"{path}: missing data block")

    for key in REQUIRED_PROVENANCE_KEYS:
        if key not in provenance:
            raise SnapshotError(f"{path}: provenance is missing {key!r}")
        value = provenance[key]
        if value is None or (isinstance(value, str) and not value.strip()):
            raise SnapshotError(f"{path}: provenance {key!r} is blank")
    if provenance["version"] != SNAPSHOT_FORMAT_VERSION:
        raise SnapshotError(
            f"{path}: provenance version is {provenance['version']!r}, "
            f"expected {SNAPSHOT_FORMAT_VERSION}"
        )
    if not _DATE_RE.match(str(provenance["retrieved"])):
        raise SnapshotError(
            f"{path}: provenance retrieved is not YYYY-MM-DD: "
            f"{provenance['retrieved']!r}"
        )

    checksum = provenance.get("sha256_of_data")
    if not isinstance(checksum, str) or not _SHA256_RE.match(checksum):
        raise SnapshotError(f"{path}: provenance sha256_of_data is missing or malformed")
    actual = data_checksum(data)
    if actual != checksum:
        raise SnapshotError(
            f"{path}: data does not match provenance sha256_of_data "
            f"({actual} != {checksum}); regenerate with {provenance['generator']}"
        )

    snapshot = Snapshot(name=name, path=path, provenance=provenance, data=data)
    _CACHE[path] = snapshot
    return snapshot
