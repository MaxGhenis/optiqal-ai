"""Tests for the frozen graph declarations and kernel protocol."""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from optiqal.graph.decl import (
    Graph,
    GraphError,
    Node,
    SourceRef,
    compile_graph,
)
from optiqal.graph.kernel import (
    Capabilities,
    Determinism,
    KernelBase,
    KernelRegistry,
    KernelResult,
    Numeric,
    NumericScope,
    Tolerance,
    source_hash,
)


class _Kernel(KernelBase):
    ref = "test@1"
    capabilities = Capabilities(Determinism.DETERMINISTIC)

    def run(self, context):
        return KernelResult(context.params)


def _valid_graph() -> Graph:
    return Graph(
        name="test",
        sources=(SourceRef("input", "input", "Descriptive"),),
        nodes=(
            Node("compute", "test@1", ("input",), {"scale": 2.0}),
            Node("gate", "gate@1", ("compute",), role="gate"),
            Node("release", "release@1", ("compute", "gate"), role="release"),
        ),
    )


def test_declarations_are_frozen_and_params_are_read_only():
    node = Node("node", "test@1", params={"nested": (True, 1, 2.0, "x", None)})
    with pytest.raises(FrozenInstanceError):
        node.id = "changed"
    with pytest.raises(TypeError):
        node.params["new"] = 1


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: SourceRef("", "loader"), "non-empty"),
        (lambda: SourceRef("source", ""), "non-empty"),
        (lambda: SourceRef("source", "loader", description=1), "must be a string"),
        (lambda: Node("", "kernel@1"), "non-empty"),
        (lambda: Node("node", ""), "non-empty"),
        (lambda: Node("node", "kernel@1", inputs=["x"]), "tuple"),
        (lambda: Node("node", "kernel@1", ("x", "x")), "repeats"),
        (lambda: Node("node", "kernel@1", params={"": 1}), "non-empty"),
        (lambda: Node("node", "kernel@1", params={"x": []}), "parameters"),
        (lambda: Node("node", "kernel@1", params={"x": math.nan}), "finite"),
        (lambda: Node("node", "kernel@1", role="unknown"), "role"),
        (lambda: Graph("", (), ()), "non-empty"),
        (lambda: Graph("graph", [], ()), "tuple"),
        (lambda: Graph("graph", (), []), "tuple"),
    ],
)
def test_declaration_validation(factory, message):
    with pytest.raises(GraphError, match=message):
        factory()


def test_graph_rejects_duplicate_and_ambiguous_names():
    source = SourceRef("source", "loader")
    node = Node("node", "test@1")
    with pytest.raises(GraphError, match="repeats a source"):
        Graph("graph", (source, source), ())
    with pytest.raises(GraphError, match="repeats a node"):
        Graph("graph", (), (node, node))
    with pytest.raises(GraphError, match="ambiguous"):
        Graph("graph", (SourceRef("node", "loader"),), (node,))


def test_compile_graph_orders_by_depth_then_id_and_finds_ancestors():
    graph = _valid_graph()
    compiled = compile_graph(
        Graph(graph.name, graph.sources, tuple(reversed(graph.nodes)))
    )
    assert compiled.order == ("compute", "gate", "release")
    assert compiled.predecessors["release"] == ("compute", "gate")
    assert compiled.ancestors("release") == ("compute", "gate")
    assert compiled.node("compute").kernel == "test@1"
    assert graph.node("gate").role == "gate"
    assert graph.source("input").loader == "input"


def test_compile_graph_rejects_unknown_inputs_cycles_and_ungated_releases():
    with pytest.raises(GraphError, match="unknown input"):
        compile_graph(Graph("bad", (), (Node("node", "test@1", ("missing",)),)))
    with pytest.raises(GraphError, match="Cycle"):
        compile_graph(
            Graph(
                "cycle",
                (),
                (
                    Node("a", "test@1", ("b",)),
                    Node("b", "test@1", ("a",)),
                ),
            )
        )
    with pytest.raises(GraphError, match="gate ancestor"):
        compile_graph(
            Graph(
                "ungated",
                (),
                (
                    Node("compute", "test@1"),
                    Node("release", "release@1", ("compute",), role="release"),
                ),
            )
        )
    with pytest.raises(TypeError, match="expects a Graph"):
        compile_graph("not a graph")


def test_unknown_declaration_lookups_raise_useful_errors():
    graph = _valid_graph()
    with pytest.raises(GraphError, match="Unknown node"):
        graph.node("missing")
    with pytest.raises(GraphError, match="Unknown source"):
        graph.source("missing")
    with pytest.raises(GraphError, match="Unknown node"):
        compile_graph(graph).ancestors("missing")


def test_tolerance_and_numeric_scope_validation():
    assert Tolerance(1, 2) == Tolerance(1.0, 2.0)
    for kwargs in (
        {"rtol": -1},
        {"atol": math.inf},
        {"rtol": True},
        {},
    ):
        with pytest.raises((TypeError, ValueError)):
            Tolerance(**kwargs)
    with pytest.raises(ValueError, match="requires"):
        Capabilities(
            Determinism.DETERMINISTIC,
            numeric=Numeric.TOLERANCE_BOUND,
        )
    with pytest.raises(ValueError, match="Only"):
        Capabilities(
            Determinism.DETERMINISTIC,
            tolerance=Tolerance(atol=1e-9),
        )
    scope = NumericScope(
        Numeric.TOLERANCE_BOUND,
        Tolerance(rtol=1e-6),
        platform="arm64/darwin/py3.14",
    )
    assert scope.platform == "arm64/darwin/py3.14"
    with pytest.raises(ValueError, match="requires a platform"):
        NumericScope(Numeric.PLATFORM_BITWISE)
    with pytest.raises(ValueError, match="cannot be platform"):
        NumericScope(platform="platform")


def test_capabilities_validate_roles_and_dependencies():
    with pytest.raises(TypeError, match="Determinism"):
        Capabilities("deterministic")
    with pytest.raises(TypeError, match="Numeric"):
        Capabilities(Determinism.DETERMINISTIC, numeric="bitwise")
    with pytest.raises(ValueError, match="role"):
        Capabilities(Determinism.DETERMINISTIC, role="other")
    with pytest.raises(TypeError, match="dependencies"):
        Capabilities(Determinism.DETERMINISTIC, dependencies=["numpy"])
    with pytest.raises(ValueError, match="repeat"):
        Capabilities(Determinism.DETERMINISTIC, dependencies=("numpy", "numpy"))


def test_kernel_result_validates_mappings_and_artifacts():
    result = KernelResult({"value": 1}, {"fact": True}, {"raw": b"bytes"})
    assert result.artifacts["raw"] == b"bytes"
    with pytest.raises(TypeError, match="receipt"):
        KernelResult(None, receipt=[])
    with pytest.raises(TypeError, match="artifact names"):
        KernelResult(None, artifacts={"": b"x"})
    with pytest.raises(TypeError, match="must be bytes"):
        KernelResult(None, artifacts={"x": "not bytes"})


def test_registry_exercises_registration_lookup_and_identity_errors():
    registry = KernelRegistry()
    kernel = _Kernel()
    assert registry.register(kernel) is kernel
    assert registry.register(kernel) is kernel
    assert registry.refs() == ("test@1",)
    assert registry.get("test@1") is kernel
    assert registry.implementation_hash("test@1") == kernel.implementation_hash()
    assert registry.as_mapping()["test@1"] is kernel
    with pytest.raises(KeyError, match="No kernel"):
        registry.get("missing@1")

    other = _Kernel()
    with pytest.raises(Exception, match="already registered"):
        registry.register(other)

    class BadRef(_Kernel):
        ref = ""

    with pytest.raises(Exception, match="non-empty"):
        KernelRegistry().register(BadRef())

    with pytest.raises(Exception, match="Kernel protocol"):
        KernelRegistry().register(object())


def test_source_hash_is_stable_and_dependency_sensitive():
    assert source_hash(_Kernel) == source_hash(_Kernel)
    assert source_hash(_Kernel, dependencies=("numpy",)) != source_hash(_Kernel)
    with pytest.raises(ValueError, match="not installed"):
        source_hash(_Kernel, dependencies=("surely-not-an-installed-package",))
