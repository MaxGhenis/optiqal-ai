"""Render a graph run as a self-contained, interactive HTML document."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from collections.abc import Sequence
from html import escape
from pathlib import Path

from .decl import CompiledGraph, compile_graph
from .errors import ManifestError
from .manifest import RunManifest, load
from .view import describe

__all__ = ["explain", "main"]

_BOX_WIDTH = 220
_BOX_HEIGHT = 82
_COLUMN_GAP = 290
_ROW_GAP = 128
_MARGIN_X = 64
_MARGIN_Y = 54


def _text(value: object) -> str:
    return escape(_html_string(value), quote=False)


def _attribute(value: object) -> str:
    return escape(_html_string(value), quote=True)


def _html_string(value: object) -> str:
    """Replace control characters that cannot safely appear in HTML text."""

    result = []
    for character in str(value):
        codepoint = ord(character)
        forbidden = (
            (codepoint < 0x20 and character not in "\t\n\r")
            or 0x7F <= codepoint <= 0x9F
            or 0xD800 <= codepoint <= 0xDFFF
        )
        result.append("\N{REPLACEMENT CHARACTER}" if forbidden else character)
    return "".join(result)


def _short_label(value: str, length: int = 27) -> str:
    """Fit an identifier inside a graph box without changing its detail text."""

    flattened = " ".join(value.split())
    if len(flattened) <= length:
        return flattened
    return flattened[: length - 1] + "…"


def _layout(
    compiled: CompiledGraph,
) -> tuple[dict[str, tuple[int, int]], int, int]:
    """Lay out sources and nodes in deterministic dependency columns."""

    depths = {source.name: 0 for source in compiled.graph.sources}
    for node_id in compiled.order:
        node = compiled.node(node_id)
        depths[node_id] = (
            0
            if not node.inputs
            else 1 + max(depths[input_id] for input_id in node.inputs)
        )

    layers: dict[int, list[str]] = defaultdict(list)
    for identifier, depth in depths.items():
        layers[depth].append(identifier)
    for identifiers in layers.values():
        identifiers.sort()

    positions: dict[str, tuple[int, int]] = {}
    for depth, identifiers in sorted(layers.items()):
        for row, identifier in enumerate(identifiers):
            positions[identifier] = (
                _MARGIN_X + depth * _COLUMN_GAP,
                _MARGIN_Y + row * _ROW_GAP,
            )

    maximum_depth = max(layers, default=0)
    maximum_rows = max((len(identifiers) for identifiers in layers.values()), default=1)
    width = 2 * _MARGIN_X + _BOX_WIDTH + maximum_depth * _COLUMN_GAP
    height = 2 * _MARGIN_Y + _BOX_HEIGHT + (maximum_rows - 1) * _ROW_GAP
    return positions, max(width, 640), max(height, 220)


def _edge(
    source: str,
    target: str,
    positions: dict[str, tuple[int, int]],
) -> str:
    start_x, start_y = positions[source]
    end_x, end_y = positions[target]
    start_x += _BOX_WIDTH
    start_y += _BOX_HEIGHT // 2
    end_y += _BOX_HEIGHT // 2
    bend = (start_x + end_x) // 2
    attributes = f'data-from="{_attribute(source)}" data-to="{_attribute(target)}"'
    return "\n".join(
        (
            f'<path class="edge" {attributes} '
            f'd="M {start_x} {start_y} C {bend} {start_y}, '
            f'{bend} {end_y}, {end_x - 10} {end_y}" />',
            f'<path class="edge-arrow" {attributes} '
            f'd="M {end_x} {end_y} L {end_x - 10} {end_y - 6} '
            f'L {end_x - 10} {end_y + 6} Z" />',
        )
    )


def _source_box(
    source_id: str,
    index: int,
    positions: dict[str, tuple[int, int]],
) -> str:
    x, y = positions[source_id]
    link_id = f"graph-source-{index}"
    detail_id = f"detail-source-{index}"
    return "\n".join(
        (
            f'<a id="{link_id}" class="graph-link source-link" '
            f'href="#{detail_id}" data-source-id="{_attribute(source_id)}" '
            f'aria-label="Show source {_attribute(source_id)} details">',
            f"<title>Source {_text(source_id)}</title>",
            f'<rect class="node-box" x="{x}" y="{y}" '
            f'width="{_BOX_WIDTH}" height="{_BOX_HEIGHT}" rx="10" />',
            f'<text class="node-title" x="{x + 14}" y="{y + 27}">'
            f"{_text(_short_label(source_id))}</text>",
            f'<text class="node-meta" x="{x + 14}" y="{y + 53}">Source</text>',
            "</a>",
        )
    )


def _node_box(
    node_id: str,
    index: int,
    manifest: RunManifest,
    positions: dict[str, tuple[int, int]],
) -> str:
    node = manifest.graph.node(node_id)
    receipt = manifest.node(node_id)
    x, y = positions[node_id]
    cache = "hit" if receipt.hit else "miss"
    if node.role == "gate":
        fact = f"Outcome: {receipt.receipt['outcome']}"
    elif node.role == "release":
        fact = f"Tier: {receipt.tier}"
    else:
        fact = "Compute node"
    link_id = f"graph-node-{index}"
    detail_id = f"detail-node-{index}"
    classes = f"graph-link node-link role-{node.role} cache-{cache}"
    label = f"{node.role.capitalize()} {node_id}, cache {cache}"
    if node.role == "gate":
        label += f", outcome {receipt.receipt['outcome']}"
    elif node.role == "release":
        label += f", tier {receipt.tier}"
    return "\n".join(
        (
            f'<a id="{link_id}" class="{classes}" href="#{detail_id}" '
            f'data-node-id="{_attribute(node_id)}" '
            f'data-cache="{cache}" aria-label="{_attribute(label)}">',
            f"<title>{_text(label)}</title>",
            f'<rect class="node-box" x="{x}" y="{y}" '
            f'width="{_BOX_WIDTH}" height="{_BOX_HEIGHT}" rx="10" />',
            f'<text class="node-title" x="{x + 14}" y="{y + 23}">'
            f"{_text(_short_label(node_id))}</text>",
            f'<text class="node-meta" x="{x + 14}" y="{y + 47}">'
            f"{node.role.capitalize()} · cache {cache}</text>",
            f'<text class="node-fact" x="{x + 14}" y="{y + 68}">{_text(fact)}</text>',
            "</a>",
        )
    )


def _source_detail(source_id: str, index: int, manifest: RunManifest) -> str:
    source = manifest.graph.source(source_id)
    detail_id = f"detail-source-{index}"
    link_id = f"graph-source-{index}"
    lines = (
        f"Source: {source.name}.",
        f"Loader: {source.loader}.",
        f"Key: {manifest.source_keys[source_id]}.",
    )
    return "\n".join(
        (
            f'<article id="{detail_id}" class="detail-card source-detail" '
            f'tabindex="-1" data-source-id="{_attribute(source_id)}">',
            f"<h3>Source: {_text(source_id)}</h3>",
            f"<pre>{_text(chr(10).join(lines))}</pre>",
            f'<a class="return-link" href="#{link_id}">Return to graph</a>',
            "</article>",
        )
    )


def _node_detail(node_id: str, index: int, manifest: RunManifest) -> str:
    detail_id = f"detail-node-{index}"
    link_id = f"graph-node-{index}"
    return "\n".join(
        (
            f'<article id="{detail_id}" class="detail-card node-detail" '
            f'tabindex="-1" data-node-id="{_attribute(node_id)}">',
            f"<h3>Node: {_text(node_id)}</h3>",
            "<p>This provenance is generated by <code>describe</code>.</p>",
            f"<pre>{_text(describe(node_id, manifest))}</pre>",
            f'<a class="return-link" href="#{link_id}">Return to graph</a>',
            "</article>",
        )
    )


def explain(manifest: RunManifest) -> str:
    """Return one static HTML page explaining every node in ``manifest``.

    Interaction uses only local fragments and CSS ``:target``. This keeps the
    saved page auditable and usable offline without scripts or resources.
    """

    if not isinstance(manifest, RunManifest):
        raise TypeError("explain expects a RunManifest")
    compiled = compile_graph(manifest.graph)
    positions, width, height = _layout(compiled)
    sources = tuple(sorted(source.name for source in manifest.graph.sources))
    nodes = compiled.order

    edges = [
        _edge(input_id, node_id, positions)
        for node_id in nodes
        for input_id in manifest.graph.node(node_id).inputs
    ]
    source_boxes = [
        _source_box(source_id, index, positions)
        for index, source_id in enumerate(sources)
    ]
    node_boxes = [
        _node_box(node_id, index, manifest, positions)
        for index, node_id in enumerate(nodes)
    ]
    source_details = [
        _source_detail(source_id, index, manifest)
        for index, source_id in enumerate(sources)
    ]
    node_details = [
        _node_detail(node_id, index, manifest) for index, node_id in enumerate(nodes)
    ]

    gate_count = sum(node.role == "gate" for node in manifest.graph.nodes)
    release_count = sum(node.role == "release" for node in manifest.graph.nodes)
    edge_count = sum(len(node.inputs) for node in manifest.graph.nodes)
    graph_name = _text(manifest.graph.name)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Graph run: {graph_name}</title>
<style>
:root {{ color-scheme: light; font-family: system-ui, sans-serif; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; color: #172033; background: #f4f6fa; line-height: 1.45; }}
main {{ max-width: 1240px; margin: 0 auto; padding: 28px 22px 48px; }}
h1, h2, h3 {{ line-height: 1.2; }}
h1 {{ margin: 0 0 8px; font-size: 1.8rem; }}
h2 {{ margin-top: 30px; font-size: 1.25rem; }}
h3 {{ margin-top: 0; font-size: 1.05rem; }}
.run-key {{ overflow-wrap: anywhere; color: #4f5b70; }}
.summary {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; padding: 0; list-style: none; }}
.summary li, .legend span {{ border: 1px solid #ccd3df; border-radius: 999px; background: #fff; padding: 5px 10px; }}
.graph-scroll {{ overflow: auto; border: 1px solid #c5ccda; border-radius: 12px; background: #fff; }}
svg {{ display: block; min-width: 100%; }}
.edge {{ fill: none; stroke: #8b96a9; stroke-width: 2; }}
.edge-arrow {{ fill: #8b96a9; }}
.graph-link {{ color: inherit; outline: none; }}
.node-box {{ fill: #fff; stroke: #7c879a; stroke-width: 2; }}
.source-link .node-box {{ fill: #edf1f8; stroke-dasharray: 6 4; }}
.role-gate .node-box {{ fill: #fff8df; stroke: #aa7a00; }}
.role-release .node-box {{ fill: #ebf7ef; stroke: #31764a; }}
.cache-hit .node-box {{ stroke-width: 4; }}
.graph-link:hover .node-box, .graph-link:focus .node-box {{ stroke: #1559c5; filter: drop-shadow(0 2px 3px #9da8bb); }}
.node-title {{ font-size: 15px; font-weight: 700; fill: #172033; }}
.node-meta {{ font-size: 12px; fill: #4f5b70; }}
.node-fact {{ font-size: 12px; font-weight: 600; fill: #172033; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; color: #4f5b70; font-size: .9rem; }}
.detail-stack {{ min-height: 190px; }}
.detail-card {{ display: none; border: 1px solid #c5ccda; border-radius: 12px; background: #fff; padding: 18px; scroll-margin-top: 20px; }}
.detail-card:target {{ display: block; }}
.detail-stack:has(.detail-card:target) .detail-placeholder {{ display: none; }}
.detail-placeholder {{ border: 1px dashed #aab3c2; border-radius: 12px; background: #fff; padding: 28px; color: #4f5b70; }}
pre {{ margin: 12px 0; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font-family: ui-monospace, monospace; font-size: .88rem; }}
.return-link {{ color: #1559c5; }}
</style>
</head>
<body>
<main>
<header>
<h1>Graph run: {graph_name}</h1>
<div class="run-key">Manifest key: {_text(manifest.key)}</div>
</header>
<ul class="summary" aria-label="Run summary">
<li>{len(nodes)} nodes</li>
<li>{edge_count} edges</li>
<li>{manifest.hit_count} cache hits</li>
<li>{manifest.miss_count} cache misses</li>
<li>{gate_count} gates</li>
<li>{release_count} release nodes</li>
</ul>
<h2>Computation graph</h2>
<div class="legend" aria-label="Graph legend">
<span>Dashed: source</span><span>Yellow: gate</span><span>Green: release</span><span>Thick border: cache hit</span>
</div>
<div class="graph-scroll">
<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="graph-title graph-description">
<title id="graph-title">Computation graph for {graph_name}</title>
<desc id="graph-description">Directed dependencies from sources through compute and gate nodes to release nodes. Select a node to read its provenance.</desc>
<g class="edges" aria-hidden="true">
{chr(10).join(edges)}
</g>
<g class="sources">
{chr(10).join(source_boxes)}
</g>
<g class="nodes">
{chr(10).join(node_boxes)}
</g>
</svg>
</div>
<h2>Node details</h2>
<section class="detail-stack" aria-label="Selected provenance">
<p class="detail-placeholder">Select a graph node to reveal its description.</p>
{chr(10).join(source_details)}
{chr(10).join(node_details)}
</section>
</main>
</body>
</html>
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m optiqal.graph.explain",
        description="Render a saved Optiqal graph manifest as self-contained HTML.",
    )
    parser.add_argument(
        "manifest", type=Path, help="Path to a saved manifest JSON file."
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Load a manifest named on the command line and write its HTML to stdout."""

    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        manifest = load(arguments.manifest)
    except ManifestError as error:
        parser.error(str(error))
    sys.stdout.write(explain(manifest))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through the module CLI
    raise SystemExit(main())
