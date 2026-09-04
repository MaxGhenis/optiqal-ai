"""Deterministic execution and memoization for compiled Optiqal graphs.

Where the Optiqal interface is silent, this follows Microcosm's runtime
choices: ``require`` preflights the complete graph before invoking a kernel,
semantic cache corruption is never treated as a miss, gate exceptions become
portable failure evidence, and ``forbid`` performs no store reads.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType

import numpy as np

from . import keys as graph_keys
from .canonical import _restore_json, canonical_json
from .decl import GATE_OUTCOMES, CompiledGraph, Node
from .errors import NodeRejectedError, StoreMissError
from .kernel import (
    Capabilities,
    Kernel,
    KernelContext,
    KernelRegistry,
    KernelResult,
    Numeric,
    NumericScope,
    Tolerance,
)
from .keys import _source_projection, artifact_key, node_key, seed, source_key
from .manifest import NodeReceipt, RunManifest
from .store import ContentStore, ResumePolicy, StoredResult

__all__ = ["run_graph"]

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_GIT_OID = re.compile(r"[0-9a-f]{40,64}\Z")
_RESUME_POLICIES = ("auto", "require", "forbid")


@dataclass(frozen=True)
class _KernelIdentity:
    ref: str
    capabilities: Capabilities
    implementation: str

    def implementation_hash(self) -> str:
        return self.implementation


@dataclass(frozen=True)
class _NodePlan:
    node: Node
    kernel: Kernel
    implementation: str
    key: str
    seed: int
    input_keys: Mapping[str, str]
    numerics: Mapping[str, NumericScope]
    output_scope: NumericScope


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _engine_commit() -> str:
    """Return the checkout commit without making it part of content identity."""

    repository = Path(__file__).resolve().parents[3]
    try:
        result = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    commit = result.stdout.strip()
    return commit if _GIT_OID.fullmatch(commit) is not None else "unknown"


def _freeze(value: object) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return _freeze(value.value)
    if isinstance(value, np.ndarray):
        contiguous = np.array(value, copy=True, order="C", subok=False)
        immutable = np.frombuffer(
            contiguous.tobytes(order="C"), dtype=contiguous.dtype
        ).reshape(contiguous.shape)
        return immutable
    if isinstance(value, np.generic):
        return _freeze(value.item())
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(child) for child in value)
    raise TypeError(f"cannot freeze {type(value).__name__}")


def _canonical_copy(value: object, label: str) -> object:
    """Validate and detach a value through the store's canonical grammar."""

    try:
        restored = _restore_json(json.loads(canonical_json(value)))
        return _freeze(restored)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        raise NodeRejectedError(f"{label} is not canonical: {error}") from error


def _loaded_sources(
    compiled: CompiledGraph,
    sources: object,
) -> Mapping[str, object]:
    """Resolve either loaded content or a source-loader registry."""

    from .sources import DEFAULT_SOURCE_LOADERS, SourceLoaderRegistry, load_sources

    if sources is None:
        loaded = load_sources(compiled.graph, DEFAULT_SOURCE_LOADERS)
    elif isinstance(sources, SourceLoaderRegistry):
        loaded = load_sources(compiled.graph, sources)
    elif isinstance(sources, Mapping):
        loaded = sources
    else:
        raise TypeError("sources must be a mapping, SourceLoaderRegistry, or None")

    declared_names = {source.name for source in compiled.graph.sources}
    supplied_names = set(loaded)
    extra = sorted(str(name) for name in supplied_names - declared_names)
    if extra:
        raise ValueError(f"Sources were supplied but not declared: {extra}")
    normalized: dict[str, object] = {}
    for source in compiled.graph.sources:
        try:
            content = loaded[source.name]
        except KeyError as error:
            raise KeyError(
                f"No content supplied for source {source.name!r}."
            ) from error
        normalized[source.name] = _canonical_copy(
            _source_projection(content), f"Source {source.name!r}"
        )
    return MappingProxyType(normalized)


def _scope_for_capabilities(
    capabilities: Capabilities, fingerprint: str
) -> NumericScope:
    if capabilities.numeric is Numeric.BITWISE:
        return NumericScope()
    if capabilities.numeric is Numeric.PLATFORM_BITWISE:
        return NumericScope(Numeric.PLATFORM_BITWISE, platform=fingerprint)
    return NumericScope(
        Numeric.TOLERANCE_BOUND,
        tolerance=capabilities.tolerance,
    )


def _merge_scopes(
    capabilities: Capabilities,
    inputs: Mapping[str, NumericScope],
    fingerprint: str,
) -> NumericScope:
    """Return the loosest promise made by this writer and its inputs.

    The frozen interface does not order numeric classes or compose tolerance
    bounds. We use the Microcosm-style conservative choice: tolerance-bound is
    loosest and combines componentwise maxima; platform-bitwise is next and
    carries the run fingerprint; bitwise is strongest.
    """

    scopes = (_scope_for_capabilities(capabilities, fingerprint), *inputs.values())
    tolerance_scopes = [
        scope for scope in scopes if scope.numeric is Numeric.TOLERANCE_BOUND
    ]
    if tolerance_scopes:
        tolerances = [scope.tolerance for scope in tolerance_scopes]
        if any(tolerance is None for tolerance in tolerances):  # pragma: no cover
            raise NodeRejectedError("A tolerance-bound scope has no tolerance")
        tolerance = Tolerance(
            rtol=max(item.rtol for item in tolerances if item is not None),
            atol=max(item.atol for item in tolerances if item is not None),
        )
        inherited_platform = any(scope.platform is not None for scope in scopes)
        return NumericScope(
            Numeric.TOLERANCE_BOUND,
            tolerance=tolerance,
            platform=fingerprint if inherited_platform else None,
        )
    if any(scope.numeric is Numeric.PLATFORM_BITWISE for scope in scopes):
        return NumericScope(Numeric.PLATFORM_BITWISE, platform=fingerprint)
    return NumericScope()


def _build_plan(
    compiled: CompiledGraph,
    registry: KernelRegistry,
    source_keys: Mapping[str, str],
    fingerprint: str,
) -> tuple[_NodePlan, ...]:
    keys: dict[str, str] = {}
    scopes: dict[str, NumericScope] = {
        source.name: NumericScope() for source in compiled.graph.sources
    }
    plans: list[_NodePlan] = []
    for node_id in compiled.order:
        node = compiled.node(node_id)
        try:
            kernel = registry.get(node.kernel)
        except KeyError as error:
            raise NodeRejectedError(
                f"Node {node.id!r} references unregistered kernel {node.kernel!r}."
            ) from error
        capabilities = kernel.capabilities
        if capabilities.role != node.role:
            raise NodeRejectedError(
                f"Node {node.id!r} has role {node.role!r}, but kernel "
                f"{node.kernel!r} declares {capabilities.role!r}."
            )
        implementation = kernel.implementation_hash()
        if (
            not isinstance(implementation, str)
            or _HASH.fullmatch(implementation) is None
        ):
            raise NodeRejectedError(
                f"Kernel {node.kernel!r} returned a non-SHA-256 implementation hash."
            )
        resolved_keys = {
            input_id: (
                source_keys[input_id] if input_id in source_keys else keys[input_id]
            )
            for input_id in node.inputs
        }
        input_scopes = {input_id: scopes[input_id] for input_id in node.inputs}
        identity_kernel = _KernelIdentity(
            ref=kernel.ref,
            capabilities=capabilities,
            implementation=implementation,
        )
        identity = node_key(
            node,
            resolved_keys,
            identity_kernel,
            fingerprint=fingerprint,
        )
        output_scope = _merge_scopes(capabilities, input_scopes, fingerprint)
        keys[node.id] = identity
        scopes[node.id] = output_scope
        plans.append(
            _NodePlan(
                node=node,
                kernel=kernel,
                implementation=implementation,
                key=identity,
                seed=seed(identity),
                input_keys=MappingProxyType(resolved_keys),
                numerics=MappingProxyType(input_scopes),
                output_scope=output_scope,
            )
        )
    return tuple(plans)


def _validate_result(node: Node, result: object) -> KernelResult:
    if not isinstance(result, KernelResult):
        raise NodeRejectedError(
            f"Kernel {node.kernel!r} returned {type(result).__name__}, "
            "not KernelResult."
        )
    if "tier" in result.receipt or (
        isinstance(result.value, Mapping) and "tier" in result.value
    ):
        raise NodeRejectedError(f"Kernel {node.kernel!r} may not set tier.")
    if isinstance(result.value, Mapping) and "verification_state" in result.value:
        raise NodeRejectedError(
            f"Kernel {node.kernel!r} may only set verification_state in a gate receipt."
        )
    if node.role != "gate" and "verification_state" in result.receipt:
        raise NodeRejectedError(
            f"Kernel {node.kernel!r} may only set verification_state in a gate receipt."
        )
    if node.role == "gate":
        if "outcome" not in result.receipt or "evidence" not in result.receipt:
            raise NodeRejectedError(
                f"Gate {node.id!r} must record outcome and evidence."
            )
        outcome = result.receipt["outcome"]
        if outcome not in GATE_OUTCOMES:
            raise NodeRejectedError(
                f"Gate {node.id!r} returned invalid outcome {outcome!r}."
            )
        verification = result.receipt.get("verification_state")
        if verification is not None and verification not in {
            "sourced",
            "authored",
            "heuristic",
        }:
            raise NodeRejectedError(
                f"Gate {node.id!r} returned invalid verification state "
                f"{verification!r}."
            )
        if node.kernel == "evidence_gate@1" and verification is None:
            raise NodeRejectedError(
                f"Evidence gate {node.id!r} must record verification_state."
            )
    value = _canonical_copy(result.value, f"Node {node.id!r} value")
    receipt = _canonical_copy(result.receipt, f"Node {node.id!r} receipt")
    if not isinstance(receipt, Mapping):  # pragma: no cover - KernelResult guards it
        raise NodeRejectedError(f"Node {node.id!r} receipt is not a mapping.")
    return KernelResult(value=value, receipt=receipt, artifacts=result.artifacts)


def _gate_failure(node: Node, error: Exception) -> KernelResult:
    error_type = type(error).__name__
    receipt: dict[str, object] = {
        "outcome": "fail",
        "evidence": {
            "exception_type": error_type,
            "message": str(error),
        },
    }
    if node.kernel == "evidence_gate@1":
        receipt["verification_state"] = "heuristic"
    return KernelResult(
        value=None,
        receipt=receipt,
    )


def _run_kernel(plan: _NodePlan, values: Mapping[str, object]) -> KernelResult:
    inputs = {
        input_id: _canonical_copy(
            values[input_id], f"Input {input_id!r} to node {plan.node.id!r}"
        )
        for input_id in plan.node.inputs
    }
    before = canonical_json(inputs)
    generator = np.random.Generator(np.random.PCG64(plan.seed))
    context = KernelContext(
        node=plan.node,
        inputs=inputs,
        params=plan.node.params,
        rng=generator,
        numerics=plan.numerics,
    )
    try:
        result = plan.kernel.run(context)
    except Exception as error:
        if plan.node.role == "gate":
            result = _gate_failure(plan.node, error)
        else:
            raise NodeRejectedError(
                f"Node {plan.node.id!r} raised {type(error).__name__}: {error}"
            ) from error
    if canonical_json(inputs) != before:
        raise NodeRejectedError(f"Node {plan.node.id!r} mutated its input context.")
    return _validate_result(plan.node, result)


def _stored_result(node: Node, stored: StoredResult) -> KernelResult:
    return _validate_result(
        node,
        KernelResult(
            value=stored.value,
            receipt=stored.receipt,
            artifacts=stored.artifacts,
        ),
    )


def _tier(
    compiled: CompiledGraph, node_id: str, receipts: Mapping[str, NodeReceipt]
) -> str:
    gates = [
        ancestor
        for ancestor in compiled.ancestors(node_id)
        if compiled.node(ancestor).role == "gate"
    ]
    outcomes = [receipts[gate].receipt["outcome"] for gate in gates]
    if "unreached" in outcomes:
        return "unreached"
    if all(outcome in {"pass", "not_applicable"} for outcome in outcomes):
        return "certified"
    return "evidence"


def _artifact_checksums(artifacts: Mapping[str, bytes]) -> Mapping[str, str]:
    return MappingProxyType(
        {
            name: hashlib.sha256(payload).hexdigest()
            for name, payload in artifacts.items()
        }
    )


def run_graph(
    compiled: CompiledGraph,
    registry: KernelRegistry,
    store: ContentStore,
    sources: object = None,
    resume: ResumePolicy = "auto",
) -> RunManifest:
    """Execute ``compiled`` with content reuse and return complete provenance."""

    if not isinstance(compiled, CompiledGraph):
        raise TypeError("run_graph expects a CompiledGraph")
    if not isinstance(registry, KernelRegistry):
        raise TypeError("run_graph expects a KernelRegistry")
    if not isinstance(store, ContentStore):
        raise TypeError("run_graph expects a ContentStore")
    if resume not in _RESUME_POLICIES:
        raise ValueError(f"resume must be one of {_RESUME_POLICIES}, got {resume!r}")

    started_at = _now()
    run_started = time.perf_counter()
    engine_commit = _engine_commit()
    loaded_sources = _loaded_sources(compiled, sources)
    source_keys = MappingProxyType(
        {
            source.name: source_key(source.name, loaded_sources[source.name])
            for source in compiled.graph.sources
        }
    )
    fingerprint = graph_keys.platform_fingerprint()
    plans = _build_plan(compiled, registry, source_keys, fingerprint)

    preflight: dict[str, StoredResult] = {}
    if resume == "require":
        misses: list[str] = []
        for plan in plans:
            try:
                preflight[plan.node.id] = store.get_record(artifact_key(plan.key))
            except StoreMissError:
                misses.append(plan.node.id)
        if misses:
            raise StoreMissError(
                "resume='require' found cache misses before execution: "
                + ", ".join(repr(node_id) for node_id in misses)
            )

    values: dict[str, object] = dict(loaded_sources)
    receipts: dict[str, NodeReceipt] = {}
    for plan in plans:
        node_started = time.perf_counter()
        hit = False
        stored: StoredResult | None = None
        if resume == "require":
            stored = preflight[plan.node.id]
            hit = True
        elif resume == "auto":
            try:
                stored = store.get_record(artifact_key(plan.key))
                hit = True
            except StoreMissError:
                pass

        if stored is None:
            result = _run_kernel(plan, values)
            store.put(
                artifact_key(plan.key),
                result.value,
                result.artifacts,
                result.receipt,
                verify_existing=resume != "forbid",
            )
            checksums = _artifact_checksums(result.artifacts)
        else:
            result = _stored_result(plan.node, stored)
            checksums = stored.artifact_checksums

        values[plan.node.id] = result.value
        tier = (
            _tier(compiled, plan.node.id, receipts)
            if plan.node.role == "release"
            else None
        )
        receipts[plan.node.id] = NodeReceipt(
            key=plan.key,
            kernel_ref=plan.node.kernel,
            kernel_impl_hash=plan.implementation,
            hit=hit,
            receipt=result.receipt,
            seed=plan.seed,
            capabilities=plan.kernel.capabilities,
            value=result.value,
            input_keys=plan.input_keys,
            numerics=plan.numerics,
            artifact_checksums=checksums,
            tier=tier,
            wall_time=time.perf_counter() - node_started,
        )

    finished_at = _now()
    wall_time = time.perf_counter() - run_started
    if not math.isfinite(wall_time):  # pragma: no cover - monotonic clock invariant
        raise NodeRejectedError("Run clock returned a non-finite duration")
    return RunManifest(
        graph=compiled.graph,
        engine_commit=engine_commit,
        platform_fingerprint=fingerprint,
        source_keys=source_keys,
        nodes=receipts,
        started_at=started_at,
        finished_at=finished_at,
        wall_time=wall_time,
    )
