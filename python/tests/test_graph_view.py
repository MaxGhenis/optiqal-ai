"""Tests for deterministic, self-contained graph node descriptions."""

from __future__ import annotations

import pytest

from optiqal.graph.decl import Graph, GraphError, Node, SourceRef
from optiqal.graph.kernel import Capabilities, Determinism, NumericScope
from optiqal.graph.keys import node_key, seed
from optiqal.graph.manifest import NodeReceipt, RunManifest
from optiqal.graph.view import describe


class _Kernel:
    def __init__(self, node: Node, implementation: str):
        self.ref = node.kernel
        self.capabilities = Capabilities(Determinism.DETERMINISTIC, role=node.role)
        self._implementation = implementation

    def implementation_hash(self) -> str:
        return self._implementation


def _receipt(
    node: Node,
    implementation: str,
    inputs: dict[str, str],
    *,
    hit: bool = False,
    facts: dict[str, object] | None = None,
    tier: str | None = None,
) -> NodeReceipt:
    kernel = _Kernel(node, implementation)
    identity = node_key(node, inputs, kernel)
    return NodeReceipt(
        key=identity,
        kernel_ref=node.kernel,
        kernel_impl_hash=implementation,
        hit=hit,
        receipt={} if facts is None else facts,
        seed=seed(identity),
        capabilities=kernel.capabilities,
        value={"node": node.id},
        input_keys=inputs,
        numerics={input_id: NumericScope() for input_id in inputs},
        tier=tier,
    )


def _manifest() -> RunManifest:
    graph = Graph(
        "view-test",
        (SourceRef("prior:alpha", "priors"),),
        (
            Node("root", "root@1"),
            Node(
                "compute",
                "compute@1",
                ("prior:alpha", "root"),
                {"z": (2, "two"), "a": True},
            ),
            Node("gate", "gate@1", ("compute",), role="gate"),
            Node(
                "release",
                "release@1",
                ("compute", "gate"),
                role="release",
            ),
        ),
    )
    source_keys = {"prior:alpha": "f" * 64}
    root = _receipt(graph.node("root"), "0" * 64, {})
    compute = _receipt(
        graph.node("compute"),
        "1" * 64,
        {"prior:alpha": source_keys["prior:alpha"], "root": root.key},
        hit=True,
    )
    gate = _receipt(
        graph.node("gate"),
        "2" * 64,
        {"compute": compute.key},
        facts={"outcome": "pass", "evidence": "fixture"},
    )
    release = _receipt(
        graph.node("release"),
        "3" * 64,
        {"compute": compute.key, "gate": gate.key},
        tier="certified",
    )
    return RunManifest(
        graph=graph,
        engine_commit="deadbeef",
        platform_fingerprint="arm64/darwin/py3.14",
        source_keys=source_keys,
        nodes={
            "root": root,
            "compute": compute,
            "gate": gate,
            "release": release,
        },
    )


def test_describe_release_is_deterministic_complete_and_under_40_lines():
    manifest = _manifest()
    release = manifest.graph.node("release")
    receipt = manifest.node("release")
    expected = "\n".join(
        (
            'Node: "release".',
            'Kernel: "release@1".',
            f"Implementation hash: {'3' * 64}.",
            'Inputs: "compute" (node identifier "compute") has key '
            f'{receipt.input_keys["compute"]}; "gate" (node identifier "gate") '
            f"has key {receipt.input_keys['gate']}.",
            "Parameters: {}.",
            'Seed derivation: int.from_bytes(sha256(b"seed\\0" + '
            'node_key.encode("utf-8")).digest()[:8], "little"), with '
            f'node_key="{receipt.key}", gives {receipt.seed}.',
            "Cache: miss.",
            'Ancestral gate outcomes: "gate" = "pass".',
            "Tier: certified.",
        )
    )
    assert describe("release", manifest) == expected
    assert describe(release, manifest) == expected
    assert len(expected.splitlines()) < 40


def test_describe_source_params_hit_and_empty_sections():
    manifest = _manifest()
    compute = describe("compute", manifest)
    assert (
        'Inputs: "prior:alpha" (source identifier "prior:alpha"; loader "priors") '
        "has key " + "f" * 64
    ) in compute
    assert '"root" (node identifier "root")' in compute
    assert 'Parameters: {"a":true,"z":[2,"two"]}.' in compute
    assert "Cache: hit." in compute
    assert "Ancestral gate outcomes: none." in compute
    assert "Tier: not applicable." in compute

    root = describe("root", manifest)
    assert "Inputs: none." in root
    assert "Parameters: {}." in root


def test_describe_rejects_unknown_foreign_and_malformed_arguments():
    manifest = _manifest()
    with pytest.raises(GraphError, match="Unknown node"):
        describe("missing", manifest)
    with pytest.raises(ValueError, match="does not match"):
        describe(Node("release", "other@1"), manifest)
    with pytest.raises(TypeError, match="Node or node id"):
        describe(42, manifest)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="RunManifest"):
        describe("release", object())  # type: ignore[arg-type]
