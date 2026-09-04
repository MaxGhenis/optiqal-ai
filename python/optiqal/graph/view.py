"""Deterministic, one-screen descriptions of graph node provenance."""

from __future__ import annotations

from .canonical import canonical_json
from .decl import Node, compile_graph
from .manifest import RunManifest

__all__ = ["describe"]


def _json(value: object) -> str:
    """Render one canonical value without allowing it to add output lines."""

    return canonical_json(value).decode("utf-8")


def _resolve(node: Node | str, manifest: RunManifest) -> Node:
    if not isinstance(manifest, RunManifest):
        raise TypeError("describe expects a RunManifest")
    if isinstance(node, str):
        return manifest.graph.node(node)
    if not isinstance(node, Node):
        raise TypeError("describe expects a Node or node id")
    declared = manifest.graph.node(node.id)
    if node != declared:
        raise ValueError(f"Node {node.id!r} does not match the manifest declaration")
    return declared


def describe(node: Node | str, manifest: RunManifest) -> str:
    """Describe one node using only its embedded declaration and run receipt.

    The compact, sentence-case form deliberately keeps collections on one line,
    so even a wide graph remains below the interface's 40-line ceiling.
    """

    declared = _resolve(node, manifest)
    receipt = manifest.node(declared.id)
    compiled = compile_graph(manifest.graph)
    sources = {source.name: source for source in manifest.graph.sources}
    inputs = []
    for input_id in declared.inputs:
        if input_id in sources:
            identity = f"source identifier {_json(input_id)}; loader {_json(sources[input_id].loader)}"
        else:
            identity = f"node identifier {_json(input_id)}"
        inputs.append(
            f"{_json(input_id)} ({identity}) has key {receipt.input_keys[input_id]}"
        )
    gates = [
        f"{_json(ancestor)} = {_json(manifest.node(ancestor).receipt['outcome'])}"
        for ancestor in compiled.ancestors(declared.id)
        if compiled.node(ancestor).role == "gate"
    ]
    lines = [
        f"Node: {_json(declared.id)}.",
        f"Kernel: {_json(receipt.kernel_ref)}.",
        f"Implementation hash: {receipt.kernel_impl_hash}.",
        f"Inputs: {'; '.join(inputs) if inputs else 'none'}.",
        f"Parameters: {_json(declared.params)}.",
        'Seed derivation: int.from_bytes(sha256(b"seed\\0" + '
        f'node_key.encode("utf-8")).digest()[:8], "little"), with '
        f"node_key={_json(receipt.key)}, gives {receipt.seed}.",
        f"Cache: {'hit' if receipt.hit else 'miss'}.",
        f"Ancestral gate outcomes: {'; '.join(gates) if gates else 'none'}.",
        f"Tier: {receipt.tier if receipt.tier is not None else 'not applicable'}.",
    ]
    return "\n".join(lines)
