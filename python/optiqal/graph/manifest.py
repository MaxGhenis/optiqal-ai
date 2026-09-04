"""Portable, content-keyed provenance for Optiqal graph runs."""

from __future__ import annotations

import json
import math
import os
import re
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Self

import numpy as np

from .canonical import _restore_json, canonical_json, sha256_domain
from .decl import GATE_OUTCOMES, TIERS, Graph, Node, SourceRef, compile_graph
from .errors import ManifestError
from .kernel import Capabilities, Determinism, Numeric, NumericScope, Tolerance
from .keys import node_key as derive_node_key
from .keys import seed as derive_seed

__all__ = [
    "Decision",
    "NodeReceipt",
    "RunManifest",
    "load",
    "load_certified",
    "save",
]

_SCHEMA_VERSION = 1
_KEY = re.compile(r"[0-9a-f]{64}\Z")
_VERIFICATION_STATES = frozenset({"sourced", "authored", "heuristic"})


def _reserved_field(
    value: object,
    forbidden: frozenset[str],
    *,
    path: str,
    allowed_here: frozenset[str] = frozenset(),
) -> tuple[str, str] | None:
    """Return the first recursively reserved mapping field and its path."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in forbidden and key not in allowed_here:
                return key, child_path
            found = _reserved_field(child, forbidden, path=child_path)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            found = _reserved_field(
                child,
                forbidden,
                path=f"{path}[{index}]",
            )
            if found is not None:
                return found
    return None


def _freeze(value: object) -> object:
    """Detach canonical values into recursively immutable containers."""

    if isinstance(value, Enum):
        return _freeze(value.value)
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("manifest values must be finite")
        return value
    if isinstance(value, np.ndarray):
        contiguous = np.array(value, copy=True, order="C", subok=False)
        if (
            np.issubdtype(contiguous.dtype, np.inexact)
            and not np.isfinite(contiguous).all()
        ):
            raise ValueError("manifest arrays must be finite")
        return np.frombuffer(
            contiguous.tobytes(order="C"), dtype=contiguous.dtype
        ).reshape(contiguous.shape)
    if isinstance(value, np.generic):
        return _freeze(value.item())
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("manifest mappings require string keys")
            result[key] = _freeze(child)
        return MappingProxyType(result)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    raise TypeError(f"manifest cannot serialize {type(value).__name__}")


def _string(value: object, label: str, *, nonempty: bool = False) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        qualifier = "non-empty " if nonempty else ""
        raise TypeError(f"{label} must be a {qualifier}string")
    return value


def _exact_fields(
    value: object, expected: set[str], label: str
) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"{label} fields do not match schema; missing={missing}, extra={extra}"
        )
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _integer(value: object, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be an integer")
    return value


@dataclass(frozen=True)
class _RecordedKernel:
    """Minimal kernel identity used to authenticate a restored node receipt."""

    ref: str
    capabilities: Capabilities
    implementation: str

    def implementation_hash(self) -> str:
        return self.implementation


@dataclass(frozen=True)
class Decision(Mapping[str, str]):
    """A signed human decision carried as provenance and excluded from keys."""

    owner: str
    kind: str
    text: str
    signed_at: str
    _record: Mapping[str, str] | None = field(
        default=None, repr=False, compare=False, kw_only=True
    )

    def __post_init__(self) -> None:
        for name in ("owner", "kind", "text", "signed_at"):
            _string(getattr(self, name), f"Decision.{name}")
        if self._record is not None:
            if not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in self._record.items()
            ):
                raise TypeError("Decision records must map strings to strings")
            object.__setattr__(self, "_record", MappingProxyType(dict(self._record)))

    def _payload(self) -> dict[str, str]:
        if self._record is not None:
            return dict(self._record)
        return {
            "kind": self.kind,
            "owner": self.owner,
            "signed_at": self.signed_at,
            "text": self.text,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> Self:
        """Normalize a decision mapping into the current signed-record shape."""

        if set(value) == {"owner", "kind", "text", "signed_at"}:
            return cls(
                owner=_string(value["owner"], "Decision.owner"),
                kind=_string(value["kind"], "Decision.kind"),
                text=_string(value["text"], "Decision.text"),
                signed_at=_string(value["signed_at"], "Decision.signed_at"),
            )
        if set(value) == {"name", "owner", "signature"}:
            record = {
                "name": _string(value["name"], "Decision.name"),
                "owner": _string(value["owner"], "Decision.owner"),
                "signature": _string(value["signature"], "Decision.signature"),
            }
            return cls(
                owner=record["owner"],
                kind=record["name"],
                text=record["signature"],
                signed_at="",
                _record=record,
            )
        raise TypeError(
            "Decision mappings require owner/kind/text/signed_at or "
            "name/owner/signature fields"
        )

    def __getitem__(self, key: str) -> str:
        return self._payload()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._payload())

    def __len__(self) -> int:
        return len(self._payload())


@dataclass(frozen=True)
class NodeReceipt:
    """The complete portable receipt for one graph node."""

    key: str
    kernel_ref: str
    kernel_impl_hash: str
    hit: bool
    receipt: Mapping[str, object]
    seed: int
    capabilities: Capabilities
    value: object
    input_keys: Mapping[str, str] = field(default_factory=dict)
    numerics: Mapping[str, NumericScope] = field(default_factory=dict)
    artifact_checksums: Mapping[str, str] = field(default_factory=dict)
    tier: str | None = None
    wall_time: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or _KEY.fullmatch(self.key) is None:
            raise TypeError("NodeReceipt.key must be a lowercase SHA-256 string")
        _string(self.kernel_ref, "NodeReceipt.kernel_ref", nonempty=True)
        if (
            not isinstance(self.kernel_impl_hash, str)
            or _KEY.fullmatch(self.kernel_impl_hash) is None
        ):
            raise TypeError(
                "NodeReceipt.kernel_impl_hash must be a lowercase SHA-256 string"
            )
        if not isinstance(self.hit, bool):
            raise TypeError("NodeReceipt.hit must be a bool")
        if (
            not isinstance(self.seed, int)
            or isinstance(self.seed, bool)
            or not 0 <= self.seed < 2**64
        ):
            raise TypeError("NodeReceipt.seed must be an unsigned 64-bit int")
        if self.seed != derive_seed(self.key):
            raise ValueError("NodeReceipt.seed must be derived from its node key")
        if not isinstance(self.capabilities, Capabilities):
            raise TypeError("NodeReceipt.capabilities must be Capabilities")
        if not isinstance(self.receipt, Mapping):
            raise TypeError("NodeReceipt.receipt must be a mapping")
        frozen_receipt = _freeze(self.receipt)
        if not isinstance(frozen_receipt, Mapping):  # pragma: no cover - guarded above
            raise TypeError("NodeReceipt.receipt must be a mapping")
        frozen_value = _freeze(self.value)
        object.__setattr__(self, "receipt", frozen_receipt)
        object.__setattr__(self, "value", frozen_value)
        value_reserved = _reserved_field(
            frozen_value,
            frozenset({"tier", "verification_state"}),
            path="value",
        )
        if value_reserved is not None:
            name, path = value_reserved
            if name == "tier":
                raise ValueError(f"Kernel values may not set tier at {path}")
            raise ValueError(
                f"verification_state may only appear in a gate receipt, not {path}"
            )
        receipt_reserved = _reserved_field(
            frozen_receipt,
            frozenset({"tier", "verification_state"}),
            path="receipt",
            allowed_here=(
                frozenset({"verification_state"})
                if self.capabilities.role == "gate"
                else frozenset()
            ),
        )
        if receipt_reserved is not None:
            name, path = receipt_reserved
            if name == "tier":
                raise ValueError(f"Kernel receipts may not set tier at {path}")
            raise ValueError(
                f"verification_state may only appear at the root of a gate receipt, "
                f"not {path}"
            )
        if self.capabilities.role == "gate":
            if "outcome" not in frozen_receipt or "evidence" not in frozen_receipt:
                raise ValueError("A gate receipt requires outcome and evidence")
            if frozen_receipt["outcome"] not in GATE_OUTCOMES:
                raise ValueError(
                    f"Gate outcome must be one of {GATE_OUTCOMES}, "
                    f"got {frozen_receipt['outcome']!r}"
                )
            verification = frozen_receipt.get("verification_state")
            if verification is not None and (
                not isinstance(verification, str)
                or verification not in _VERIFICATION_STATES
            ):
                raise ValueError("A gate receipt has an invalid verification state")
            if self.kernel_ref == "evidence_gate@1" and verification is None:
                raise ValueError(
                    "An evidence_gate@1 receipt requires verification_state"
                )

        inputs: dict[str, str] = {}
        for input_id, identity in self.input_keys.items():
            name = _string(input_id, "input id", nonempty=True)
            if not isinstance(identity, str) or _KEY.fullmatch(identity) is None:
                raise TypeError("Input keys must be lowercase SHA-256 strings")
            inputs[name] = identity
        object.__setattr__(self, "input_keys", MappingProxyType(inputs))
        numerics: dict[str, NumericScope] = {}
        for input_id, scope in self.numerics.items():
            if not isinstance(input_id, str) or not isinstance(scope, NumericScope):
                raise TypeError("NodeReceipt.numerics must map strings to NumericScope")
            numerics[input_id] = scope
        if set(numerics) != set(inputs):
            raise ValueError("NodeReceipt.numerics must cover exactly its input keys")
        object.__setattr__(self, "numerics", MappingProxyType(numerics))
        checksums: dict[str, str] = {}
        for name, checksum in self.artifact_checksums.items():
            if not isinstance(name, str) or not name:
                raise TypeError("Artifact checksum names must be non-empty strings")
            if not isinstance(checksum, str) or _KEY.fullmatch(checksum) is None:
                raise TypeError("Artifact checksums must be lowercase SHA-256 strings")
            checksums[name] = checksum
        object.__setattr__(self, "artifact_checksums", MappingProxyType(checksums))

        if self.tier is not None and self.tier not in TIERS:
            raise ValueError(f"NodeReceipt.tier must be one of {TIERS} or None")
        if self.capabilities.role == "release" and self.tier is None:
            raise ValueError("A release NodeReceipt requires a derived tier")
        if self.capabilities.role != "release" and self.tier is not None:
            raise ValueError("Only a release NodeReceipt may carry a tier")
        if isinstance(self.wall_time, bool) or not isinstance(
            self.wall_time, (int, float)
        ):
            raise TypeError("NodeReceipt.wall_time must be numeric")
        wall_time = float(self.wall_time)
        if not math.isfinite(wall_time) or wall_time < 0:
            raise ValueError("NodeReceipt.wall_time must be finite and non-negative")
        object.__setattr__(self, "wall_time", wall_time)

    @property
    def implementation_hash(self) -> str:
        """Alias for the interface's concise implementation-hash spelling."""

        return self.kernel_impl_hash

    @property
    def node_key(self) -> str:
        """Alias used by identity-oriented callers."""

        return self.key

    @property
    def store_hit(self) -> bool:
        """Alias used by store-oriented callers."""

        return self.hit

    def _portable(self, *, run_fields: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "artifact_checksums": self.artifact_checksums,
            "capabilities": _capabilities_payload(self.capabilities),
            "input_keys": self.input_keys,
            "kernel_impl_hash": self.kernel_impl_hash,
            "kernel_ref": self.kernel_ref,
            "key": self.key,
            "numerics": {
                input_id: _numeric_scope_payload(scope)
                for input_id, scope in self.numerics.items()
            },
            "receipt": self.receipt,
            "seed": self.seed,
            "tier": self.tier,
            "value": self.value,
        }
        if run_fields:
            payload.update({"hit": self.hit, "wall_time": self.wall_time})
        return payload


@dataclass(frozen=True)
class RunManifest:
    """One complete graph run, including keyed facts and run-level observations."""

    graph: Graph
    engine_commit: str
    platform_fingerprint: str
    source_keys: Mapping[str, str]
    nodes: Mapping[str, NodeReceipt]
    decisions: tuple[Decision, ...] = ()
    started_at: str = ""
    finished_at: str = ""
    wall_time: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.graph, Graph):
            raise TypeError("RunManifest.graph must be a Graph")
        compiled = compile_graph(self.graph)
        _string(self.engine_commit, "RunManifest.engine_commit")
        _string(
            self.platform_fingerprint,
            "RunManifest.platform_fingerprint",
            nonempty=True,
        )
        for name in ("started_at", "finished_at"):
            _string(getattr(self, name), f"RunManifest.{name}")
        if isinstance(self.wall_time, bool) or not isinstance(
            self.wall_time, (int, float)
        ):
            raise TypeError("RunManifest.wall_time must be numeric")
        wall_time = float(self.wall_time)
        if not math.isfinite(wall_time) or wall_time < 0:
            raise ValueError("RunManifest.wall_time must be finite and non-negative")
        object.__setattr__(self, "wall_time", wall_time)

        sources: dict[str, str] = {}
        for name, identity in self.source_keys.items():
            source_name = _string(name, "source name", nonempty=True)
            if not isinstance(identity, str) or _KEY.fullmatch(identity) is None:
                raise TypeError("Source keys must be lowercase SHA-256 strings")
            sources[source_name] = identity
        expected_sources = {source.name for source in self.graph.sources}
        if set(sources) != expected_sources:
            raise ValueError("RunManifest.source_keys must cover every declared source")
        object.__setattr__(self, "source_keys", MappingProxyType(sources))

        nodes: dict[str, NodeReceipt] = {}
        for node_id, receipt in self.nodes.items():
            if not isinstance(node_id, str) or not isinstance(receipt, NodeReceipt):
                raise TypeError("RunManifest.nodes must map strings to NodeReceipt")
            nodes[node_id] = receipt
        expected_nodes = {node.id for node in self.graph.nodes}
        if set(nodes) != expected_nodes:
            raise ValueError("RunManifest.nodes must cover every declared node")
        for node in self.graph.nodes:
            if nodes[node.id].kernel_ref != node.kernel:
                raise ValueError(f"Receipt for {node.id!r} names a different kernel")
            if nodes[node.id].capabilities.role != node.role:
                raise ValueError(f"Receipt for {node.id!r} names a different role")
            receipt = nodes[node.id]
            if set(receipt.input_keys) != set(node.inputs):
                raise ValueError(
                    f"Receipt for {node.id!r} must list exactly its declared inputs"
                )
            for input_id in node.inputs:
                expected_key = (
                    sources[input_id] if input_id in sources else nodes[input_id].key
                )
                if receipt.input_keys[input_id] != expected_key:
                    raise ValueError(
                        f"Receipt for {node.id!r} binds the wrong key for "
                        f"input {input_id!r}"
                    )
            recorded_kernel = _RecordedKernel(
                ref=receipt.kernel_ref,
                capabilities=receipt.capabilities,
                implementation=receipt.kernel_impl_hash,
            )
            expected_node_key = derive_node_key(
                node,
                receipt.input_keys,
                recorded_kernel,
                fingerprint=self.platform_fingerprint,
            )
            if receipt.key != expected_node_key:
                raise ValueError(
                    f"Receipt for {node.id!r} does not match its declared identity"
                )
            if node.role == "release":
                gates = [
                    ancestor
                    for ancestor in compiled.ancestors(node.id)
                    if self.graph.node(ancestor).role == "gate"
                ]
                expected_tier = _tier_from_outcomes(
                    [nodes[gate].receipt["outcome"] for gate in gates]
                )
                if receipt.tier != expected_tier:
                    raise ValueError(
                        f"Receipt for {node.id!r} tier does not match its gate ancestry"
                    )
        object.__setattr__(self, "nodes", MappingProxyType(nodes))

        normalized_decisions: list[Decision] = []
        for decision in self.decisions:
            if isinstance(decision, Decision):
                normalized_decisions.append(decision)
            elif isinstance(decision, Mapping):
                normalized_decisions.append(Decision.from_mapping(decision))
            else:
                raise TypeError("RunManifest.decisions must contain Decision records")
        object.__setattr__(self, "decisions", tuple(normalized_decisions))

    @property
    def graph_name(self) -> str:
        return self.graph.name

    @property
    def hit_count(self) -> int:
        return sum(receipt.hit for receipt in self.nodes.values())

    @property
    def miss_count(self) -> int:
        return len(self.nodes) - self.hit_count

    @property
    def content_addressed(self) -> Mapping[str, object]:
        """The deterministic projection hashed by :attr:`key`.

        Following Microcosm amendment 18, complete portable node receipts are
        hashed except executor observations (hit and wall time). Human
        decisions and all run-level fields are excluded.
        """

        return MappingProxyType(
            {
                "nodes": {
                    node_id: self.nodes[node_id]._portable(run_fields=False)
                    for node_id in sorted(self.nodes)
                }
            }
        )

    @property
    def key(self) -> str:
        return sha256_domain("manifest", canonical_json(self.content_addressed))

    def node(self, node_id: str) -> NodeReceipt:
        """Return one node receipt."""

        try:
            return self.nodes[node_id]
        except KeyError as error:
            raise KeyError(f"Manifest has no receipt for node {node_id!r}.") from error

    receipt = node

    def __getitem__(self, node_id: str) -> NodeReceipt:
        return self.node(node_id)

    def to_json_bytes(self) -> bytes:
        """Serialize the complete portable manifest as canonical JSON."""

        payload = {
            "decisions": tuple(decision._payload() for decision in self.decisions),
            "engine_commit": self.engine_commit,
            "finished_at": self.finished_at,
            "graph": _graph_payload(self.graph),
            "hit_count": self.hit_count,
            "key": self.key,
            "miss_count": self.miss_count,
            "nodes": {
                node_id: receipt._portable() for node_id, receipt in self.nodes.items()
            },
            "platform_fingerprint": self.platform_fingerprint,
            "schema_version": _SCHEMA_VERSION,
            "source_keys": self.source_keys,
            "started_at": self.started_at,
            "wall_time": self.wall_time,
        }
        return canonical_json(payload)

    def to_json(self) -> str:
        return self.to_json_bytes().decode("utf-8")

    @classmethod
    def from_json(cls, value: str | bytes | bytearray) -> Self:
        """Restore a manifest and verify its content key and run counters."""

        if isinstance(value, (bytes, bytearray)):
            try:
                value = bytes(value).decode("utf-8")
            except UnicodeDecodeError as error:
                raise ManifestError("Manifest is not UTF-8 JSON.") from error
        if not isinstance(value, str):
            raise TypeError("RunManifest.from_json expects str or bytes")
        try:
            raw = json.loads(value)
            raw = _restore_json(raw)
        except (json.JSONDecodeError, ValueError) as error:
            raise ManifestError("Manifest is not valid canonical data.") from error
        if not isinstance(raw, dict):
            raise ManifestError("Manifest JSON must contain an object.")
        expected_fields = {
            "decisions",
            "engine_commit",
            "finished_at",
            "graph",
            "hit_count",
            "key",
            "miss_count",
            "nodes",
            "platform_fingerprint",
            "schema_version",
            "source_keys",
            "started_at",
            "wall_time",
        }
        try:
            _exact_fields(raw, expected_fields, "manifest")
        except (TypeError, ValueError) as error:
            raise ManifestError(f"Manifest fields are malformed: {error}") from error
        if (
            type(raw["schema_version"]) is not int
            or raw["schema_version"] != _SCHEMA_VERSION
        ):
            raise ManifestError(
                f"Unsupported manifest schema version {raw['schema_version']!r}."
            )
        try:
            graph = _graph_from_payload(raw["graph"])
            nodes_raw = raw["nodes"]
            decisions_raw = raw["decisions"]
            if not isinstance(nodes_raw, dict) or not isinstance(decisions_raw, list):
                raise TypeError
            manifest = cls(
                graph=graph,
                engine_commit=_string(raw["engine_commit"], "engine_commit"),
                platform_fingerprint=_string(
                    raw["platform_fingerprint"],
                    "platform_fingerprint",
                    nonempty=True,
                ),
                source_keys=_string_mapping(raw["source_keys"], "source_keys"),
                nodes={
                    node_id: _node_receipt_from_payload(payload)
                    for node_id, payload in nodes_raw.items()
                },
                decisions=tuple(Decision.from_mapping(item) for item in decisions_raw),
                started_at=_string(raw["started_at"], "started_at"),
                finished_at=_string(raw["finished_at"], "finished_at"),
                wall_time=_number(raw["wall_time"], "wall_time"),
            )
            hit_count = _integer(raw["hit_count"], "hit_count")
            miss_count = _integer(raw["miss_count"], "miss_count")
            serialized_key = _string(raw["key"], "key", nonempty=True)
            if _KEY.fullmatch(serialized_key) is None:
                raise ValueError("key must be a lowercase SHA-256 string")
        except (KeyError, OverflowError, TypeError, ValueError) as error:
            raise ManifestError(f"Manifest fields are malformed: {error}") from error
        if hit_count < 0 or miss_count < 0:
            raise ManifestError("Manifest hit/miss counters must be non-negative.")
        if hit_count != manifest.hit_count or miss_count != manifest.miss_count:
            raise ManifestError("Manifest hit/miss counters do not match its nodes.")
        if serialized_key != manifest.key:
            raise ManifestError(
                "Manifest content key mismatch: deterministic provenance was altered."
            )
        return manifest

    def save(self, path: str | Path) -> Path:
        """Atomically write this manifest to ``path``."""

        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
        try:
            staged.write_bytes(self.to_json_bytes())
            os.replace(staged, destination)
        finally:
            try:
                staged.unlink()
            except FileNotFoundError:
                pass
        return destination

    @classmethod
    def load(cls, path: str | Path) -> Self:
        """Load and content-validate a saved manifest."""

        try:
            content = Path(path).read_bytes()
        except OSError as error:
            raise ManifestError(f"Cannot read manifest at {path}.") from error
        return cls.from_json(content)

    @classmethod
    def load_certified(cls, path: str | Path) -> Self:
        """Load a manifest and refuse every non-certified release."""

        manifest = cls.load(path)
        manifest.validate_certified()
        return manifest

    def validate_certified(self) -> None:
        """Re-derive release tiers and reject failed public ancestry."""

        compiled = compile_graph(self.graph)
        releases = [node for node in self.graph.nodes if node.role == "release"]
        if not releases:
            raise ManifestError("A certified manifest requires at least one release.")
        for node in self.graph.nodes:
            receipt = self.nodes[node.id]
            if node.role == "gate":
                outcome = receipt.receipt.get("outcome")
                if outcome not in GATE_OUTCOMES:
                    raise ManifestError(
                        f"Gate {node.id!r} has invalid outcome {outcome!r}."
                    )
                if "evidence" not in receipt.receipt:
                    raise ManifestError(f"Gate {node.id!r} has no evidence.")
                verification = receipt.receipt.get("verification_state")
                if verification is not None and (
                    not isinstance(verification, str)
                    or verification not in _VERIFICATION_STATES
                ):
                    raise ManifestError(
                        f"Gate {node.id!r} has invalid verification state."
                    )
                if node.kernel == "evidence_gate@1" and verification is None:
                    raise ManifestError(
                        f"Evidence gate {node.id!r} has no verification state."
                    )
        for node in releases:
            gates = [
                ancestor
                for ancestor in compiled.ancestors(node.id)
                if self.graph.node(ancestor).role == "gate"
            ]
            outcomes = [self.nodes[gate].receipt.get("outcome") for gate in gates]
            expected = _tier_from_outcomes(outcomes)
            if self.nodes[node.id].tier != expected:
                raise ManifestError(
                    f"Release {node.id!r} tier does not match its gate ancestry."
                )
            verification_states = {
                self.nodes[gate].receipt.get("verification_state") for gate in gates
            }
            if "heuristic" in verification_states:
                raise ManifestError(
                    f"Release {node.id!r} has heuristic evidence ancestry."
                )
            if expected != "certified":
                raise ManifestError(
                    f"Release {node.id!r} is {expected}-tier, not certified."
                )


def _tier_from_outcomes(outcomes: list[object]) -> str:
    if "unreached" in outcomes:
        return "unreached"
    if all(outcome in {"pass", "not_applicable"} for outcome in outcomes):
        return "certified"
    return "evidence"


def _tolerance_payload(value: Tolerance | None) -> object:
    return None if value is None else {"atol": value.atol, "rtol": value.rtol}


def _capabilities_payload(value: Capabilities) -> dict[str, object]:
    return {
        "dependencies": value.dependencies,
        "determinism": value.determinism.value,
        "numeric": value.numeric.value,
        "role": value.role,
        "tolerance": _tolerance_payload(value.tolerance),
    }


def _capabilities_from_payload(value: object) -> Capabilities:
    payload = _exact_fields(
        value,
        {"dependencies", "determinism", "numeric", "role", "tolerance"},
        "capabilities",
    )
    dependencies = payload["dependencies"]
    if not isinstance(dependencies, list):
        raise TypeError("capability dependencies must be an array")
    return Capabilities(
        determinism=Determinism(_string(payload["determinism"], "determinism")),
        numeric=Numeric(_string(payload["numeric"], "numeric")),
        role=_string(payload["role"], "role"),
        dependencies=tuple(
            _string(item, "dependency", nonempty=True) for item in dependencies
        ),
        tolerance=_tolerance_from_payload(payload["tolerance"]),
    )


def _tolerance_from_payload(value: object) -> Tolerance | None:
    if value is None:
        return None
    payload = _exact_fields(value, {"atol", "rtol"}, "tolerance")
    return Tolerance(
        rtol=_number(payload["rtol"], "tolerance.rtol"),
        atol=_number(payload["atol"], "tolerance.atol"),
    )


def _numeric_scope_payload(value: NumericScope) -> dict[str, object]:
    return {
        "numeric": value.numeric.value,
        "platform": value.platform,
        "tolerance": _tolerance_payload(value.tolerance),
    }


def _numeric_scope_from_payload(value: object) -> NumericScope:
    payload = _exact_fields(
        value, {"numeric", "platform", "tolerance"}, "numeric scope"
    )
    platform_value = payload["platform"]
    if platform_value is not None:
        platform_value = _string(platform_value, "numeric platform", nonempty=True)
    return NumericScope(
        numeric=Numeric(_string(payload["numeric"], "scope numeric")),
        tolerance=_tolerance_from_payload(payload["tolerance"]),
        platform=platform_value,
    )


def _graph_payload(graph: Graph) -> dict[str, object]:
    return {
        "name": graph.name,
        "nodes": [
            {
                "citation": node.citation,
                "description": node.description,
                "id": node.id,
                "inputs": node.inputs,
                "kernel": node.kernel,
                "params": node.params,
                "role": node.role,
            }
            for node in sorted(graph.nodes, key=lambda item: item.id)
        ],
        "sources": [
            {
                "description": source.description,
                "loader": source.loader,
                "name": source.name,
            }
            for source in sorted(graph.sources, key=lambda item: item.name)
        ],
    }


def _param(value: object) -> object:
    if isinstance(value, list):
        return tuple(_param(child) for child in value)
    return value


def _graph_from_payload(value: object) -> Graph:
    payload = _exact_fields(value, {"name", "nodes", "sources"}, "graph")
    sources = payload["sources"]
    nodes = payload["nodes"]
    if not isinstance(sources, list) or not isinstance(nodes, list):
        raise TypeError("graph sources and nodes must be arrays")
    if not all(isinstance(item, Mapping) for item in sources):
        raise TypeError("graph sources must contain objects")
    if not all(isinstance(item, Mapping) for item in nodes):
        raise TypeError("graph nodes must contain objects")
    return Graph(
        name=_string(payload["name"], "graph name", nonempty=True),
        sources=tuple(
            SourceRef(
                name=_string(source["name"], "source name", nonempty=True),
                loader=_string(source["loader"], "source loader", nonempty=True),
                description=_string(source["description"], "source description"),
            )
            for source in (
                _exact_fields(
                    item,
                    {"description", "loader", "name"},
                    "graph source",
                )
                for item in sources
            )
        ),
        nodes=tuple(
            Node(
                id=_string(node["id"], "node id", nonempty=True),
                kernel=_string(node["kernel"], "node kernel", nonempty=True),
                inputs=_inputs(node["inputs"]),
                params={
                    key: _param(child)
                    for key, child in _mapping(node["params"], "params").items()
                },
                role=_string(node["role"], "node role"),
                description=_string(node["description"], "node description"),
                citation=_string(node["citation"], "node citation"),
            )
            for node in (
                _exact_fields(
                    item,
                    {
                        "citation",
                        "description",
                        "id",
                        "inputs",
                        "kernel",
                        "params",
                        "role",
                    },
                    "graph node",
                )
                for item in nodes
            )
        ),
    )


def _inputs(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise TypeError("node inputs must be an array")
    return tuple(_string(item, "node input", nonempty=True) for item in value)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be an object")
    return value


def _string_mapping(value: object, label: str) -> dict[str, str]:
    mapping = _mapping(value, label)
    return {
        _string(key, f"{label} key", nonempty=True): _string(
            child, f"{label} value", nonempty=True
        )
        for key, child in mapping.items()
    }


def _node_receipt_from_payload(value: object) -> NodeReceipt:
    payload = _exact_fields(
        value,
        {
            "artifact_checksums",
            "capabilities",
            "hit",
            "input_keys",
            "kernel_impl_hash",
            "kernel_ref",
            "key",
            "numerics",
            "receipt",
            "seed",
            "tier",
            "value",
            "wall_time",
        },
        "node receipt",
    )
    numerics_raw = _mapping(payload["numerics"], "numerics")
    return NodeReceipt(
        key=_string(payload["key"], "node key", nonempty=True),
        kernel_ref=_string(payload["kernel_ref"], "kernel ref", nonempty=True),
        kernel_impl_hash=_string(
            payload["kernel_impl_hash"], "kernel implementation", nonempty=True
        ),
        hit=payload["hit"],
        receipt=_mapping(payload["receipt"], "receipt"),
        seed=_integer(payload["seed"], "seed"),
        capabilities=_capabilities_from_payload(payload["capabilities"]),
        value=payload["value"],
        input_keys=_string_mapping(payload["input_keys"], "input_keys"),
        numerics={
            input_id: _numeric_scope_from_payload(scope)
            for input_id, scope in numerics_raw.items()
        },
        artifact_checksums=_string_mapping(
            payload["artifact_checksums"], "artifact_checksums"
        ),
        tier=payload["tier"],
        wall_time=_number(payload["wall_time"], "wall_time"),
    )


def save(manifest: RunManifest, path: str | Path) -> Path:
    """Module-level manifest save helper."""

    if not isinstance(manifest, RunManifest):
        raise TypeError("save expects a RunManifest")
    return manifest.save(path)


def load(path: str | Path) -> RunManifest:
    """Module-level manifest load helper."""

    return RunManifest.load(path)


def load_certified(path: str | Path) -> RunManifest:
    """Module-level certified-manifest loader."""

    return RunManifest.load_certified(path)
