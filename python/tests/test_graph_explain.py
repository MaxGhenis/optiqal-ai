"""Tests for the static HTML graph explorer and its command line."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import replace
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import pytest

from optiqal.graph.decl import Graph, Node, SourceRef
from optiqal.graph.explain import explain
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


class _PageAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))


def _receipt(
    node: Node,
    implementation: str,
    input_keys: dict[str, str],
    *,
    hit: bool = False,
    facts: dict[str, object] | None = None,
    tier: str | None = None,
) -> NodeReceipt:
    kernel = _Kernel(node, implementation)
    identity = node_key(node, input_keys, kernel)
    return NodeReceipt(
        key=identity,
        kernel_ref=node.kernel,
        kernel_impl_hash=implementation,
        hit=hit,
        receipt={} if facts is None else facts,
        seed=seed(identity),
        capabilities=kernel.capabilities,
        value={"node": node.id},
        input_keys=input_keys,
        numerics={input_id: NumericScope() for input_id in input_keys},
        tier=tier,
    )


def _manifest() -> RunManifest:
    source_name = 'input<&"'
    compute_id = 'compute<&"'
    graph = Graph(
        "unsafe <script>alert(1)</script>",
        (SourceRef(source_name, 'fixture<&"'),),
        (
            Node(
                "release-review",
                "release@1",
                (compute_id, "gate-fail"),
                role="release",
            ),
            Node("gate-pass", "gate@1", (compute_id,), role="gate"),
            Node("root", "root@1"),
            Node(compute_id, "compute@1", (source_name, "root"), {"label": "<&"}),
            Node("gate-fail", "gate@1", (compute_id,), role="gate"),
            Node(
                "release-certified",
                "release@1",
                (compute_id, "gate-pass"),
                role="release",
            ),
        ),
    )
    source_keys = {source_name: "f" * 64}
    root = _receipt(graph.node("root"), "0" * 64, {}, hit=True)
    compute = _receipt(
        graph.node(compute_id),
        "1" * 64,
        {source_name: source_keys[source_name], "root": root.key},
    )
    gate_pass = _receipt(
        graph.node("gate-pass"),
        "2" * 64,
        {compute_id: compute.key},
        facts={"outcome": "pass", "evidence": "<verified>"},
    )
    gate_fail = _receipt(
        graph.node("gate-fail"),
        "3" * 64,
        {compute_id: compute.key},
        hit=True,
        facts={"outcome": "fail", "evidence": "not enough evidence"},
    )
    certified = _receipt(
        graph.node("release-certified"),
        "4" * 64,
        {compute_id: compute.key, "gate-pass": gate_pass.key},
        hit=True,
        tier="certified",
    )
    review = _receipt(
        graph.node("release-review"),
        "5" * 64,
        {compute_id: compute.key, "gate-fail": gate_fail.key},
        tier="evidence",
    )
    return RunManifest(
        graph=graph,
        engine_commit="deadbeef",
        platform_fingerprint="arm64/darwin/py3.14",
        source_keys=source_keys,
        nodes={
            "root": root,
            compute_id: compute,
            "gate-pass": gate_pass,
            "gate-fail": gate_fail,
            "release-certified": certified,
            "release-review": review,
        },
    )


def test_explain_renders_every_dependency_and_provenance_fact():
    manifest = _manifest()
    page = explain(manifest)
    audit = _PageAudit()
    audit.feed(page)
    audit.close()

    node_links = {
        attributes["data-node-id"]: attributes
        for tag, attributes in audit.elements
        if tag == "a" and "node-link" in (attributes.get("class") or "")
    }
    source_links = {
        attributes["data-source-id"]: attributes
        for tag, attributes in audit.elements
        if tag == "a" and "source-link" in (attributes.get("class") or "")
    }
    edge_paths = [
        attributes
        for tag, attributes in audit.elements
        if tag == "path" and attributes.get("class") == "edge"
    ]

    assert set(node_links) == {node.id for node in manifest.graph.nodes}
    assert set(source_links) == {source.name for source in manifest.graph.sources}
    assert {
        (attributes["data-from"], attributes["data-to"]) for attributes in edge_paths
    } == {
        (input_id, node.id) for node in manifest.graph.nodes for input_id in node.inputs
    }
    assert len(edge_paths) == sum(len(node.inputs) for node in manifest.graph.nodes)

    details = {
        attributes["data-node-id"]: attributes
        for tag, attributes in audit.elements
        if tag == "article" and "data-node-id" in attributes
    }
    for node_id, attributes in node_links.items():
        assert attributes["href"] == f"#{details[node_id]['id']}"

    assert "Compute · cache miss" in page
    assert "Outcome: pass" in page
    assert "Outcome: fail" in page
    assert "Tier: certified" in page
    assert "Tier: evidence" in page
    assert f"Manifest key: {manifest.key}" in page
    for node in manifest.graph.nodes:
        assert escape(describe(node, manifest), quote=False) in page


def test_explain_is_validly_structured_escaped_and_has_no_external_resources():
    page = explain(_manifest())
    audit = _PageAudit()
    audit.feed(page)
    audit.close()

    assert page.startswith('<!doctype html>\n<html lang="en">')
    assert page.rstrip().endswith("</html>")
    assert "<svg " in page
    assert "<style>" in page
    assert "<script" not in page.lower()
    assert "<link" not in page.lower()
    assert "<img" not in page.lower()
    assert "<iframe" not in page.lower()
    assert "http://" not in page.lower()
    assert "https://" not in page.lower()
    assert "unsafe <script>" not in page
    assert "unsafe &lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert 'compute&lt;&amp;"' in page

    references = [
        value
        for _, attributes in audit.elements
        for name, value in attributes.items()
        if name
        in {
            "action",
            "data",
            "formaction",
            "href",
            "poster",
            "src",
            "srcset",
        }
        and value is not None
    ]
    assert references
    assert all(reference.startswith("#") for reference in references)
    assert "url(" not in page.lower()
    assert "@import" not in page.lower()
    assert ":target" in page
    assert ":focus) #detail" not in page


def test_explain_replaces_forbidden_html_control_characters():
    manifest = _manifest()
    graph = replace(manifest.graph, name="controls\0\x01\x7f\ud800")
    controlled = replace(manifest, graph=graph)
    page = explain(controlled)
    assert "\0" not in page
    assert "\x01" not in page
    assert "\x7f" not in page
    assert "\ud800" not in page
    assert "controls\N{REPLACEMENT CHARACTER}" in page


def test_explain_handles_an_empty_graph_and_rejects_the_wrong_type():
    empty = RunManifest(
        graph=Graph("empty", (), ()),
        engine_commit="",
        platform_fingerprint="x86_64/linux/py3.12",
        source_keys={},
        nodes={},
    )
    page = explain(empty)
    assert "0 nodes" in page
    assert "0 edges" in page
    assert 'viewBox="0 0 640 220"' in page

    with pytest.raises(TypeError, match="RunManifest"):
        explain(object())  # type: ignore[arg-type]


def test_module_cli_writes_html_and_reports_manifest_errors(tmp_path):
    manifest = _manifest()
    path = manifest.save(tmp_path / "manifest.json")
    python_root = Path(__file__).parents[1]
    command = [sys.executable, "-m", "optiqal.graph.explain"]

    rendered = subprocess.run(
        [*command, str(path)],
        cwd=python_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rendered.returncode == 0
    assert rendered.stdout == explain(manifest)
    assert rendered.stderr == ""

    missing = subprocess.run(
        [*command, str(tmp_path / "missing.json")],
        cwd=python_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing.returncode == 2
    assert "usage: python -m optiqal.graph.explain" in missing.stderr
    assert "error: Cannot read manifest" in missing.stderr
