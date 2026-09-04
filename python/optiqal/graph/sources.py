"""Normative source loaders for the Optiqal computation graph.

A loader receives the complete :class:`~optiqal.graph.decl.SourceRef`, not
just its registered name.  This lets one registered loader serve both a
whole table (``studies`` or ``catalog``) and row-scoped sources such as
``study:<id>`` and ``catalog:<id>``.  Where the Optiqal interface is silent,
the registry follows Microcosm's source-codec registry: registration is
idempotent only for the same callable, lookup is exact, names are sorted,
and mapping views are read-only snapshots.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType, ModuleType
from typing import TypeAlias

import numpy as np

from .canonical import canonical_json
from .decl import DESCRIPTIVE_FIELDS, CompiledGraph, Graph, SourceRef
from .errors import GraphRuntimeError, StoreUnavailableError

__all__ = [
    "DEFAULT_SOURCE_LOADERS",
    "SOURCE_LOADERS",
    "SourceLoader",
    "SourceLoaderRegistry",
    "load_sources",
]

SourceLoader: TypeAlias = Callable[[SourceRef], object]

_CATALOG_DESCRIPTIVE_FIELDS = DESCRIPTIVE_FIELDS | {"sources"}
_PRIOR_DESCRIPTIVE_FIELDS = DESCRIPTIVE_FIELDS | {
    "calibration_sources",
    "rationale",
}
_PROFILE_FIELDS = (
    "age",
    "sex",
    "bmi_category",
    "smoking_status",
    "has_diabetes",
    "has_hypertension",
    "activity_level",
)


def _detach(
    value: object,
    *,
    descriptive_fields: frozenset[str] = DESCRIPTIVE_FIELDS,
) -> object:
    """Return detached canonical content, recursively dropping inert fields."""

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Source content contains a non-finite number.")
        return value
    if isinstance(value, np.ndarray):
        copied = np.array(value, copy=True, order="C")
        if np.issubdtype(copied.dtype, np.inexact) and not np.isfinite(copied).all():
            raise ValueError("Source content contains a non-finite NumPy array.")
        return copied
    if isinstance(value, np.generic):
        return _detach(value.item(), descriptive_fields=descriptive_fields)
    if isinstance(value, Enum):
        return _detach(value.value, descriptive_fields=descriptive_fields)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _detach(
                getattr(value, item.name), descriptive_fields=descriptive_fields
            )
            for item in fields(value)
            if item.name not in descriptive_fields
        }
    if isinstance(value, Mapping):
        detached: dict[str, object] = {}
        for name, child in value.items():
            if not isinstance(name, str):
                raise TypeError("Source content mappings require string keys.")
            if name not in descriptive_fields:
                detached[name] = _detach(child, descriptive_fields=descriptive_fields)
        return detached
    if isinstance(value, tuple):
        return tuple(
            _detach(child, descriptive_fields=descriptive_fields) for child in value
        )
    if isinstance(value, list):
        return [
            _detach(child, descriptive_fields=descriptive_fields) for child in value
        ]
    raise TypeError(
        f"Source content contains unsupported {type(value).__name__} content."
    )


def _canonical_source(
    value: object,
    *,
    descriptive_fields: frozenset[str] = DESCRIPTIVE_FIELDS,
) -> object:
    detached = _detach(value, descriptive_fields=descriptive_fields)
    canonical_json(detached)
    return detached


def _import_if_present(module_name: str) -> ModuleType | None:
    """Import an optional module, ignoring only its exact absence."""

    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name == module_name:
            return None
        raise


def _module_loader(module: ModuleType, function_name: str) -> Callable[..., object]:
    loader = getattr(module, function_name, None)
    if not callable(loader):
        raise StoreUnavailableError(
            f"{module.__name__}.{function_name} is required to load graph sources."
        )
    return loader


def _require_name(source: SourceRef, expected: str) -> None:
    if source.name != expected:
        raise GraphRuntimeError(
            f"Loader {source.loader!r} cannot load source {source.name!r}; "
            f"expected {expected!r}."
        )


def _scoped_name(source: SourceRef, *, table: str, prefix: str) -> str | None:
    if source.name == table:
        return None
    marker = f"{prefix}:"
    if source.name.startswith(marker) and len(source.name) > len(marker):
        return source.name[len(marker) :]
    raise GraphRuntimeError(
        f"Loader {source.loader!r} cannot load source {source.name!r}; expected "
        f"{table!r} or {marker!r}<id>."
    )


def _load_priors(source: SourceRef) -> object:
    _require_name(source, "priors")
    module = _import_if_present("optiqal.priors")
    if module is not None:
        return _canonical_source(
            _module_loader(module, "load_priors")(),
            descriptive_fields=_PRIOR_DESCRIPTIVE_FIELDS,
        )

    # PR A has not landed on every integration branch.  These are exactly the
    # numeric tables available in the pre-PR-A confounding module; rationale,
    # calibration citations, and source prose are deliberately not projected.
    confounding = importlib.import_module("optiqal.confounding")
    categories = {
        name: {"alpha": prior.alpha, "beta": prior.beta}
        for name, prior in confounding.CATEGORY_PRIORS.items()
    }
    content = {
        "confounding": {"categories": categories},
        "evidence_adjustments": {
            name: {"alpha_multiplier": multiplier}
            for name, multiplier in confounding.EVIDENCE_ADJUSTMENTS.items()
        },
        "study_quality_shrinkage": {
            name: {"retention": retention}
            for name, retention in confounding.STUDY_QUALITY_SHRINKAGE.items()
        },
    }
    return _canonical_source(content)


def _row_id(row: object, fallback: object = None) -> object:
    if isinstance(row, Mapping):
        return row.get("id", fallback)
    return getattr(row, "id", fallback)


def _table_by_id(raw: object, *, label: str) -> dict[str, object]:
    if isinstance(raw, Mapping):
        rows: Sequence[tuple[object, object]] = tuple(raw.items())
    elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        rows = tuple((None, row) for row in raw)
    else:
        raise TypeError(
            f"The {label} loader must return a mapping or sequence of rows."
        )

    table: dict[str, object] = {}
    for fallback, row in rows:
        identifier = _row_id(row, fallback)
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"Every {label} row must have a non-empty string id.")
        if fallback is not None and fallback != identifier:
            raise ValueError(
                f"{label.capitalize()} row {identifier!r} is mapped under {fallback!r}."
            )
        if identifier in table:
            raise ValueError(
                f"The {label} loader returned duplicate id {identifier!r}."
            )
        projected = _canonical_source(row)
        if not isinstance(projected, dict):
            raise TypeError(
                f"{label.capitalize()} row {identifier!r} is not an object."
            )
        projected.setdefault("id", identifier)
        table[identifier] = projected
    return table


def _load_studies(source: SourceRef) -> object:
    identifier = _scoped_name(source, table="studies", prefix="study")
    module = _import_if_present("optiqal.evidence")
    table = (
        {}
        if module is None
        else _table_by_id(_module_loader(module, "load_studies")(), label="study")
    )
    if identifier is None:
        return table
    try:
        return table[identifier]
    except KeyError as error:
        raise KeyError(f"Unknown study id {identifier!r}.") from error


def _snapshot_name(source: SourceRef) -> str:
    marker = "snapshot:"
    if not source.name.startswith(marker) or len(source.name) == len(marker):
        raise GraphRuntimeError(
            f"Loader {source.loader!r} requires a source named 'snapshot:<name>', "
            f"got {source.name!r}."
        )
    return source.name[len(marker) :]


def _load_snapshot(source: SourceRef) -> object:
    name = _snapshot_name(source)
    module = _import_if_present("optiqal.snapshots")
    if module is None:
        raise StoreUnavailableError(
            f"Cannot load {source.name!r}: optional module 'optiqal.snapshots' "
            "is not installed."
        )
    loaded = _module_loader(module, "load_snapshot")(name)
    if isinstance(loaded, Mapping) and "provenance" in loaded:
        if "data" not in loaded:
            raise ValueError(f"Snapshot {name!r} has provenance but no data block.")
        loaded = loaded["data"]
    elif hasattr(loaded, "provenance") and hasattr(loaded, "data"):
        loaded = getattr(loaded, "data")
    return _canonical_source(loaded)


def _catalog_entry(entry: object, identifier: object) -> dict[str, object]:
    entry_id = _row_id(entry, identifier)
    if not isinstance(entry_id, str) or not entry_id:
        raise ValueError("Every catalog entry must have a non-empty string id.")
    if identifier != entry_id:
        raise ValueError(f"Catalog entry {entry_id!r} is mapped under {identifier!r}.")
    projected = _canonical_source(entry, descriptive_fields=_CATALOG_DESCRIPTIVE_FIELDS)
    if not isinstance(projected, dict):
        raise TypeError(f"Catalog entry {entry_id!r} is not an object.")
    projected.setdefault("id", entry_id)
    study_ids = projected.setdefault("study_ids", [])
    if not isinstance(study_ids, (list, tuple)) or any(
        not isinstance(study_id, str) or not study_id for study_id in study_ids
    ):
        raise ValueError(f"Catalog entry {entry_id!r} has invalid study_ids.")
    if len(set(study_ids)) != len(study_ids):
        raise ValueError(f"Catalog entry {entry_id!r} repeats a study id.")
    projected["study_ids"] = sorted(study_ids)
    canonical_json(projected)
    return projected


def _load_catalog(source: SourceRef) -> object:
    identifier = _scoped_name(source, table="catalog", prefix="catalog")
    module = importlib.import_module("optiqal.catalog")
    loaded = _module_loader(module, "get_catalog")()
    if not isinstance(loaded, Mapping):
        raise TypeError("optiqal.catalog.get_catalog must return a mapping.")
    table: dict[str, object] = {}
    for entry_id, entry in loaded.items():
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("Catalog mappings require non-empty string ids.")
        table[entry_id] = _catalog_entry(entry, entry_id)
    if identifier is None:
        return table
    try:
        return table[identifier]
    except KeyError as error:
        raise KeyError(f"Unknown catalog id {identifier!r}.") from error


def _profile_projection(profile: object) -> dict[str, object]:
    genetic_profile = getattr(profile, "genetic_profile", None)
    if genetic_profile is not None:
        raise GraphRuntimeError("Graph profile sources refuse genetic profile data.")
    missing = [name for name in _PROFILE_FIELDS if not hasattr(profile, name)]
    if missing:
        raise TypeError(f"Generated profile is missing fields {missing!r}.")
    projected = {
        name: _detach(getattr(profile, name), descriptive_fields=frozenset())
        for name in _PROFILE_FIELDS
    }
    canonical_json(projected)
    return projected


def _profile_key(profile: Mapping[str, object]) -> str:
    diabetes = "diabetic" if profile["has_diabetes"] else "nondiabetic"
    hypertension = "hypertensive" if profile["has_hypertension"] else "normotensive"
    return "_".join(
        str(part)
        for part in (
            profile["age"],
            profile["sex"],
            profile["bmi_category"],
            profile["smoking_status"],
            diabetes,
            hypertension,
            profile["activity_level"],
        )
    )


def _load_profile(source: SourceRef) -> object:
    marker = "profile:"
    if not source.name.startswith(marker) or len(source.name) == len(marker):
        raise GraphRuntimeError(
            f"Loader {source.loader!r} requires a source named 'profile:<id>', "
            f"got {source.name!r}."
        )
    requested = source.name[len(marker) :]
    module = importlib.import_module("optiqal.profile")
    generate = _module_loader(module, "generate_all_profiles")
    found: dict[str, object] | None = None
    seen: set[str] = set()
    for profile in generate():
        projected = _profile_projection(profile)
        identifier = _profile_key(projected)
        declared = getattr(profile, "key", identifier)
        if declared != identifier:
            raise ValueError(
                f"Generated profile key {declared!r} does not match its fields "
                f"({identifier!r})."
            )
        if identifier in seen:
            raise ValueError(f"Profile generator returned duplicate id {identifier!r}.")
        seen.add(identifier)
        if identifier == requested:
            found = projected
    if found is None:
        raise KeyError(f"Unknown profile id {requested!r}.")
    return found


class SourceLoaderRegistry:
    """Named loaders for graph source declarations."""

    def __init__(self) -> None:
        self._loaders: dict[str, SourceLoader] = {}

    def register(self, name: str, loader: SourceLoader) -> SourceLoader:
        """Register and return ``loader``; repeat registration is idempotent."""

        if not isinstance(name, str) or not name:
            raise ValueError("Source loader names must be non-empty strings.")
        if not callable(loader):
            raise TypeError("Source loaders must be callable.")
        incumbent = self._loaders.get(name)
        if incumbent is not None and incumbent is not loader:
            raise ValueError(f"Source loader {name!r} is already registered.")
        self._loaders[name] = loader
        return loader

    def get(self, name: str) -> SourceLoader:
        """Resolve an exact name or a supported item-scoped spelling."""

        try:
            return self._loaders[name]
        except KeyError as error:
            if isinstance(name, str) and ":" in name:
                prefix = name.split(":", 1)[0]
                family = "studies" if prefix == "study" else prefix
                loader = self._loaders.get(family)
                if loader is not None:
                    return loader
            raise KeyError(f"No source loader registered as {name!r}.") from error

    def load(self, source: SourceRef) -> object:
        """Load and validate one declaration's detached normative content."""

        if not isinstance(source, SourceRef):
            raise TypeError("SourceLoaderRegistry.load requires a SourceRef.")
        value = self.get(source.loader)(source)
        return _canonical_source(value)

    def names(self) -> tuple[str, ...]:
        """Return registered loader names in canonical order."""

        return tuple(sorted(self._loaders))

    def as_mapping(self) -> Mapping[str, SourceLoader]:
        """Return a read-only snapshot of registered loaders."""

        return MappingProxyType(dict(self._loaders))


DEFAULT_SOURCE_LOADERS = SourceLoaderRegistry()
DEFAULT_SOURCE_LOADERS.register("catalog", _load_catalog)
DEFAULT_SOURCE_LOADERS.register("priors", _load_priors)
DEFAULT_SOURCE_LOADERS.register("profile", _load_profile)
DEFAULT_SOURCE_LOADERS.register("snapshot", _load_snapshot)
DEFAULT_SOURCE_LOADERS.register("studies", _load_studies)

# Short spelling parallel to Microcosm's SOURCE_CODECS global.
SOURCE_LOADERS = DEFAULT_SOURCE_LOADERS


def load_sources(
    graph: Graph | CompiledGraph,
    registry: SourceLoaderRegistry = DEFAULT_SOURCE_LOADERS,
) -> Mapping[str, object]:
    """Load every declared source, keyed exactly by declaration name."""

    if isinstance(graph, CompiledGraph):
        declaration = graph.graph
    elif isinstance(graph, Graph):
        declaration = graph
    else:
        raise TypeError("load_sources requires a Graph or CompiledGraph.")
    if not isinstance(registry, SourceLoaderRegistry):
        raise TypeError("registry must be a SourceLoaderRegistry.")
    loaded = {source.name: registry.load(source) for source in declaration.sources}
    return MappingProxyType(loaded)
