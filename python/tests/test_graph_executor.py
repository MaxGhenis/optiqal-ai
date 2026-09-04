"""Tests for graph execution, reuse, gates, tiers, and numeric scopes."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

import numpy as np
import pytest

from optiqal.graph.decl import Graph, Node, SourceRef, compile_graph
from optiqal.graph.errors import (
    NodeRejectedError,
    StoreCorruptError,
    StoreMissError,
)
from optiqal.graph.executor import run_graph
from optiqal.graph.kernel import (
    Capabilities,
    Determinism,
    KernelContext,
    KernelRegistry,
    KernelResult,
    Numeric,
    Tolerance,
)
from optiqal.graph.keys import artifact_key
from optiqal.graph.store import ContentStore


class _Kernel:
    def __init__(
        self,
        ref: str,
        role: str,
        function: Callable[[KernelContext], object],
        *,
        numeric: Numeric = Numeric.BITWISE,
        tolerance: Tolerance | None = None,
        implementation: str | None = None,
    ) -> None:
        self.ref = ref
        self.capabilities = Capabilities(
            Determinism.SEEDED if ref == "seeded@1" else Determinism.DETERMINISTIC,
            numeric=numeric,
            role=role,
            tolerance=tolerance,
        )
        self.function = function
        self.calls = 0
        self.contexts: list[KernelContext] = []
        self._implementation = (
            implementation or hashlib.sha256(ref.encode()).hexdigest()
        )

    def implementation_hash(self) -> str:
        return self._implementation

    def run(self, context: KernelContext) -> object:
        self.calls += 1
        self.contexts.append(context)
        return self.function(context)


def _graph(
    *,
    outcome: str = "pass",
    scale: int = 2,
    reverse: bool = False,
) -> Graph:
    nodes = (
        Node("compute", "compute@1", ("input",), {"scale": scale}),
        Node("seeded", "seeded@1", ("compute",)),
        Node("gate", "gate@1", ("seeded",), {"outcome": outcome}, role="gate"),
        Node("release", "release@1", ("seeded", "gate"), role="release"),
    )
    return Graph(
        "executor-test",
        (SourceRef("input", "fixture"),),
        tuple(reversed(nodes)) if reverse else nodes,
    )


def _registry(
    *,
    gate_function: Callable[[KernelContext], object] | None = None,
    compute_function: Callable[[KernelContext], object] | None = None,
) -> tuple[KernelRegistry, dict[str, _Kernel]]:
    def compute(context: KernelContext) -> KernelResult:
        source = context.inputs["input"]
        return KernelResult(
            source["value"] * context.params["scale"],
            {"operation": "scale"},
            {"trace": b"deterministic artifact"},
        )

    def seeded(context: KernelContext) -> KernelResult:
        return KernelResult(context.rng.normal(size=4), {"draw_count": 4})

    def gate(context: KernelContext) -> KernelResult:
        return KernelResult(
            context.inputs["seeded"],
            {
                "outcome": context.params["outcome"],
                "evidence": {"draw_count": len(context.inputs["seeded"])},
            },
        )

    def release(context: KernelContext) -> KernelResult:
        return KernelResult(
            {"mean": float(np.mean(context.inputs["seeded"]))},
            {"assembled": True},
        )

    kernels = {
        "compute": _Kernel("compute@1", "compute", compute_function or compute),
        "seeded": _Kernel("seeded@1", "compute", seeded),
        "gate": _Kernel("gate@1", "gate", gate_function or gate),
        "release": _Kernel("release@1", "release", release),
    }
    registry = KernelRegistry()
    for kernel in kernels.values():
        registry.register(kernel)
    return registry, kernels


def _run(
    tmp_path,
    *,
    outcome: str = "pass",
    resume: str = "auto",
    store: ContentStore | None = None,
    registry: KernelRegistry | None = None,
):
    if store is None:
        store = ContentStore(tmp_path / "store")
    if registry is None:
        registry, _ = _registry()
    return run_graph(
        compile_graph(_graph(outcome=outcome)),
        registry,
        store,
        {"input": {"value": 3}},
        resume=resume,
    )


def test_auto_memoizes_every_node_and_preserves_manifest_identity(tmp_path):
    store = ContentStore(tmp_path / "store")
    registry, kernels = _registry()
    first = _run(tmp_path, store=store, registry=registry)
    second = _run(tmp_path, store=store, registry=registry)

    assert first.hit_count == 0
    assert second.hit_count == len(first.nodes)
    assert first.key == second.key
    assert len(first.engine_commit) == 40
    assert all(kernel.calls == 1 for kernel in kernels.values())
    np.testing.assert_array_equal(
        first.node("seeded").value, second.node("seeded").value
    )
    assert first.node("release").tier == "certified"
    compute = first.node("compute")
    assert store.has(artifact_key(compute.key))
    assert (
        compute.artifact_checksums["trace"]
        == hashlib.sha256(b"deterministic artifact").hexdigest()
    )


def test_require_preflights_without_executing_and_then_hits(tmp_path):
    store = ContentStore(tmp_path / "store")
    registry, kernels = _registry()
    with pytest.raises(StoreMissError) as error:
        _run(tmp_path, resume="require", store=store, registry=registry)
    assert all(node_id in str(error.value) for node_id in compile_graph(_graph()).order)
    assert all(kernel.calls == 0 for kernel in kernels.values())

    _run(tmp_path, store=store, registry=registry)
    required = _run(tmp_path, resume="require", store=store, registry=registry)
    assert required.hit_count == len(required.nodes)
    assert all(kernel.calls == 1 for kernel in kernels.values())


def test_forbid_never_reads_the_store_and_marks_every_node_miss(tmp_path):
    class WriteOnlyStore(ContentStore):
        def get_record(self, key):
            raise AssertionError("forbid attempted a store read")

    store = WriteOnlyStore(tmp_path / "store")
    registry, kernels = _registry()
    manifest = _run(tmp_path, resume="forbid", store=store, registry=registry)
    assert manifest.hit_count == 0
    assert all(kernel.calls == 1 for kernel in kernels.values())


@pytest.mark.parametrize(
    ("outcome", "tier"),
    [
        ("pass", "certified"),
        ("not_applicable", "certified"),
        ("fail", "evidence"),
        ("evidence_absent", "evidence"),
        ("unreached", "unreached"),
    ],
)
def test_executor_derives_tier_from_all_gate_outcomes(tmp_path, outcome, tier):
    assert _run(tmp_path, outcome=outcome).node("release").tier == tier


def test_raising_gate_becomes_cached_failure_but_compute_exception_aborts(tmp_path):
    def raising_gate(context):
        raise LookupError(f"no evidence for {context.node.id}")

    store = ContentStore(tmp_path / "gate-store")
    registry, kernels = _registry(gate_function=raising_gate)
    first = _run(tmp_path, store=store, registry=registry)
    second = _run(tmp_path, store=store, registry=registry)
    gate = first.node("gate")
    assert gate.receipt["outcome"] == "fail"
    assert gate.receipt["evidence"]["exception_type"].endswith("LookupError")
    assert first.node("release").tier == "evidence"
    assert second.node("gate").hit
    assert kernels["gate"].calls == 1

    def raising_compute(context):
        raise RuntimeError(context.node.id)

    broken, _ = _registry(compute_function=raising_compute)
    with pytest.raises(NodeRejectedError, match="Node 'compute'.*RuntimeError"):
        _run(
            tmp_path,
            store=ContentStore(tmp_path / "compute-store"),
            registry=broken,
        )


@pytest.mark.parametrize(
    ("bad_result", "message"),
    [
        (None, "not KernelResult"),
        (KernelResult(None, {"outcome": "pass"}), "outcome and evidence"),
        (
            KernelResult(None, {"outcome": "unknown", "evidence": None}),
            "invalid outcome",
        ),
        (
            KernelResult(
                None,
                {"outcome": "pass", "evidence": None, "tier": "certified"},
            ),
            "may not set tier",
        ),
        (
            KernelResult(float("nan"), {"outcome": "pass", "evidence": None}),
            "not canonical",
        ),
    ],
)
def test_invalid_gate_results_are_rejected(tmp_path, bad_result, message):
    registry, _ = _registry(gate_function=lambda context: bad_result)
    with pytest.raises(NodeRejectedError, match=message):
        _run(tmp_path, registry=registry)


def test_registry_and_runtime_contract_errors_are_explicit(tmp_path):
    compiled = compile_graph(_graph())
    store = ContentStore(tmp_path / "store")
    registry, kernels = _registry()

    with pytest.raises(ValueError, match="resume must"):
        run_graph(compiled, registry, store, {"input": {"value": 1}}, resume="later")
    with pytest.raises(TypeError, match="CompiledGraph"):
        run_graph(_graph(), registry, store, {"input": {"value": 1}})
    with pytest.raises(TypeError, match="KernelRegistry"):
        run_graph(compiled, object(), store, {"input": {"value": 1}})
    with pytest.raises(TypeError, match="ContentStore"):
        run_graph(compiled, registry, object(), {"input": {"value": 1}})
    with pytest.raises(TypeError, match="sources"):
        run_graph(compiled, registry, store, object())
    with pytest.raises(KeyError, match="No content"):
        run_graph(compiled, registry, store, {})
    with pytest.raises(ValueError, match="not declared"):
        run_graph(
            compiled,
            registry,
            store,
            {"input": {"value": 1}, "extra": None},
        )

    missing = KernelRegistry()
    for name in ("seeded", "gate", "release"):
        missing.register(kernels[name])
    with pytest.raises(NodeRejectedError, match="unregistered kernel"):
        run_graph(compiled, missing, store, {"input": {"value": 1}})

    wrong_role, _ = _registry()
    wrong_role._kernels["gate@1"] = _Kernel("gate@1", "compute", lambda context: None)
    with pytest.raises(NodeRejectedError, match="declares 'compute'"):
        run_graph(compiled, wrong_role, store, {"input": {"value": 1}})

    bad_hash, _ = _registry()
    bad_hash._kernels["compute@1"] = _Kernel(
        "compute@1", "compute", lambda context: None, implementation="not-a-hash"
    )
    with pytest.raises(NodeRejectedError, match="non-SHA-256"):
        run_graph(compiled, bad_hash, store, {"input": {"value": 1}})


def test_noncanonical_compute_result_and_corrupt_cache_are_never_used(tmp_path):
    registry, _ = _registry(
        compute_function=lambda context: KernelResult({"bad": float("inf")})
    )
    with pytest.raises(NodeRejectedError, match="not canonical"):
        _run(tmp_path, registry=registry)

    store = ContentStore(tmp_path / "corrupt-store")
    good_registry, _ = _registry()
    manifest = _run(tmp_path, store=store, registry=good_registry)
    record = store.path(artifact_key(manifest.node("compute").key))
    record.write_bytes(record.read_bytes().replace(b'"value":6', b'"value":7'))
    with pytest.raises(StoreCorruptError):
        _run(tmp_path, store=store, registry=good_registry)


def test_context_inputs_are_detached_read_only_and_order_is_inert(tmp_path):
    observed: dict[str, object] = {}

    def inspect(context):
        observed["context"] = context
        return KernelResult(context.inputs["input"]["values"][0])

    graph = _graph()
    registry, kernels = _registry(compute_function=inspect)
    source = {"values": np.array([3.0])}
    store = ContentStore(tmp_path / "store")
    first = run_graph(compile_graph(graph), registry, store, {"input": source})
    context = observed["context"]
    assert not context.inputs["input"]["values"].flags.writeable
    with pytest.raises(ValueError):
        context.inputs["input"]["values"].setflags(write=True)
    with pytest.raises(TypeError):
        context.inputs["input"]["new"] = 1
    source["values"][0] = 99
    assert context.inputs["input"]["values"][0] == 3

    reversed_manifest = run_graph(
        compile_graph(_graph(reverse=True)),
        registry,
        store,
        {"input": {"values": np.array([3.0])}},
    )
    assert reversed_manifest.key == first.key
    assert all(receipt.hit for receipt in reversed_manifest.nodes.values())
    assert kernels["compute"].calls == 1

    def mutate_metadata(context):
        context.inputs["input"]["values"].shape = ()
        return KernelResult(3.0)

    mutating, _ = _registry(compute_function=mutate_metadata)
    with pytest.raises(NodeRejectedError, match="mutated its input"):
        run_graph(
            compile_graph(graph),
            mutating,
            ContentStore(tmp_path / "mutation-store"),
            {"input": {"values": np.array([3.0])}},
        )


def test_numeric_scopes_propagate_and_platform_partitions_keys(tmp_path, monkeypatch):
    graph = Graph(
        "numeric",
        (SourceRef("input", "fixture"),),
        (
            Node("platform", "platform@1", ("input",)),
            Node("tolerance", "tolerance@1", ("platform",)),
            Node("gate", "numeric-gate@1", ("tolerance",), role="gate"),
            Node(
                "release",
                "numeric-release@1",
                ("tolerance", "gate"),
                role="release",
            ),
        ),
    )

    platform_kernel = _Kernel(
        "platform@1",
        "compute",
        lambda context: KernelResult(context.inputs["input"]),
        numeric=Numeric.PLATFORM_BITWISE,
    )
    tolerance_kernel = _Kernel(
        "tolerance@1",
        "compute",
        lambda context: KernelResult(context.inputs["platform"]),
        numeric=Numeric.TOLERANCE_BOUND,
        tolerance=Tolerance(rtol=1e-6),
    )
    gate_kernel = _Kernel(
        "numeric-gate@1",
        "gate",
        lambda context: KernelResult(None, {"outcome": "pass", "evidence": "numeric"}),
    )
    release_kernel = _Kernel(
        "numeric-release@1",
        "release",
        lambda context: KernelResult(context.inputs["tolerance"]),
    )
    registry = KernelRegistry()
    for kernel in (
        platform_kernel,
        tolerance_kernel,
        gate_kernel,
        release_kernel,
    ):
        registry.register(kernel)

    store = ContentStore(tmp_path / "store")
    monkeypatch.setattr("optiqal.graph.keys.platform_fingerprint", lambda: "one")
    first = run_graph(compile_graph(graph), registry, store, {"input": {"value": 1}})
    assert first.node("platform").numerics["input"].numeric is Numeric.BITWISE
    assert (
        first.node("tolerance").numerics["platform"].numeric is Numeric.PLATFORM_BITWISE
    )
    release_scope = first.node("release").numerics["tolerance"]
    assert release_scope.numeric is Numeric.TOLERANCE_BOUND
    assert release_scope.tolerance == Tolerance(rtol=1e-6)
    assert release_scope.platform == "one"

    monkeypatch.setattr("optiqal.graph.keys.platform_fingerprint", lambda: "two")
    second = run_graph(compile_graph(graph), registry, store, {"input": {"value": 1}})
    assert second.hit_count == 0
    assert second.node("platform").key != first.node("platform").key
