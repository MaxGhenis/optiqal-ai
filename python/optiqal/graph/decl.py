"""Frozen declarations for Optiqal's content-addressed computation graph.

The declarations contain data only. Descriptive fields never enter identity;
everything else is normative. Where the Optiqal interface is silent, this
module follows Microcosm's choices: mappings are detached behind read-only
proxies, duplicate names are rejected at construction, and compilation emits
a canonical topological order sorted by ``(depth, id)``.

This file is a frozen interface. Its hash is recorded in
``docs/rebuild/graph-interface.lock``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from types import MappingProxyType
from typing import TypeAlias

from .errors import GraphError

__all__ = [
    "DESCRIPTIVE_FIELDS",
    "GATE_OUTCOMES",
    "ROLES",
    "TIERS",
    "CompiledGraph",
    "Graph",
    "GraphError",
    "Node",
    "Param",
    "SourceRef",
    "compile_graph",
]

Param: TypeAlias = bool | int | float | str | None | tuple["Param", ...]

DESCRIPTIVE_FIELDS = frozenset(
    {"description", "citation", "notes", "extracted_by", "source"}
)
ROLES = ("compute", "gate", "release")
GATE_OUTCOMES = ("pass", "fail", "evidence_absent", "not_applicable", "unreached")
TIERS = ("certified", "evidence", "unreached")


def _nonempty(label: str, value: object) -> None:
    if not isinstance(value, str) or not value:
        raise GraphError(f"{label} must be a non-empty string, got {value!r}.")


def _descriptive(label: str, value: object) -> None:
    if not isinstance(value, str):
        raise GraphError(f"{label} must be a string, got {type(value).__name__}.")


def _check_param(name: str, value: object) -> None:
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise GraphError(f"Parameter {name!r} is not finite: {value!r}.")
        return
    if isinstance(value, tuple):
        for index, child in enumerate(value):
            _check_param(f"{name}[{index}]", child)
        return
    raise GraphError(
        f"Parameter {name!r} has type {type(value).__name__}; parameters are "
        "bool, int, float, str, None, or tuples of those."
    )


@dataclass(frozen=True)
class SourceRef:
    """A named external input whose loader returns its normative content."""

    name: str
    loader: str
    description: str = ""

    def __post_init__(self) -> None:
        _nonempty("SourceRef.name", self.name)
        _nonempty("SourceRef.loader", self.loader)
        _descriptive("SourceRef.description", self.description)

    def normative(self) -> dict[str, object]:
        """Return the fields that enter source declaration identity."""

        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.name not in DESCRIPTIVE_FIELDS
        }


@dataclass(frozen=True)
class Node:
    """One declared pure computation, gate, or released value."""

    id: str
    kernel: str
    inputs: tuple[str, ...] = ()
    params: Mapping[str, Param] = field(default_factory=dict)
    role: str = "compute"
    description: str = ""
    citation: str = ""

    def __post_init__(self) -> None:
        _nonempty("Node.id", self.id)
        _nonempty("Node.kernel", self.kernel)
        if not isinstance(self.inputs, tuple):
            raise GraphError(f"Node {self.id!r}: inputs must be a tuple.")
        for input_id in self.inputs:
            _nonempty(f"Node {self.id!r} input", input_id)
        if len(set(self.inputs)) != len(self.inputs):
            raise GraphError(f"Node {self.id!r} repeats an input.")
        if not isinstance(self.params, Mapping):
            raise GraphError(f"Node {self.id!r}: params must be a mapping.")
        detached: dict[str, Param] = {}
        for name, value in self.params.items():
            _nonempty("Node.params key", name)
            _check_param(name, value)
            detached[name] = value
        object.__setattr__(self, "params", MappingProxyType(detached))
        if self.role not in ROLES:
            raise GraphError(
                f"Node {self.id!r}: role {self.role!r} is not one of {ROLES}."
            )
        _descriptive("Node.description", self.description)
        _descriptive("Node.citation", self.citation)

    def normative(self) -> dict[str, object]:
        """Return the declaration projection that enters the node key."""

        return {
            item.name: getattr(self, item.name)
            for item in fields(self)
            if item.name not in DESCRIPTIVE_FIELDS
        }


@dataclass(frozen=True)
class Graph:
    """A complete graph declaration; declaration order carries no meaning."""

    name: str
    sources: tuple[SourceRef, ...]
    nodes: tuple[Node, ...]

    def __post_init__(self) -> None:
        _nonempty("Graph.name", self.name)
        if not isinstance(self.sources, tuple):
            raise GraphError("Graph.sources must be a tuple.")
        if not isinstance(self.nodes, tuple):
            raise GraphError("Graph.nodes must be a tuple.")
        if not all(isinstance(source, SourceRef) for source in self.sources):
            raise GraphError("Graph.sources must contain SourceRef values.")
        if not all(isinstance(node, Node) for node in self.nodes):
            raise GraphError("Graph.nodes must contain Node values.")
        source_names = [source.name for source in self.sources]
        node_ids = [node.id for node in self.nodes]
        if len(set(source_names)) != len(source_names):
            raise GraphError("Graph repeats a source name.")
        if len(set(node_ids)) != len(node_ids):
            raise GraphError("Graph repeats a node id.")
        overlap = sorted(set(source_names).intersection(node_ids))
        if overlap:
            raise GraphError(
                "Graph source names and node ids share an ambiguous name: "
                + ", ".join(repr(name) for name in overlap)
                + "."
            )

    def node(self, node_id: str) -> Node:
        """Return one declared node with a useful unknown-node error."""

        for node in self.nodes:
            if node.id == node_id:
                return node
        raise GraphError(f"Unknown node {node_id!r}.")

    def source(self, source_name: str) -> SourceRef:
        """Return one declared source with a useful unknown-source error."""

        for source in self.sources:
            if source.name == source_name:
                return source
        raise GraphError(f"Unknown source {source_name!r}.")


@dataclass(frozen=True)
class CompiledGraph:
    """A validated declaration with derived topology and canonical order."""

    graph: Graph
    order: tuple[str, ...]
    predecessors: Mapping[str, tuple[str, ...]]
    depths: Mapping[str, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "predecessors", MappingProxyType(dict(self.predecessors))
        )
        object.__setattr__(self, "depths", MappingProxyType(dict(self.depths)))

    def node(self, node_id: str) -> Node:
        """Delegate node lookup to the declaration."""

        return self.graph.node(node_id)

    def ancestors(self, node_id: str) -> tuple[str, ...]:
        """Return all ancestral node ids in canonical compiled order."""

        self.graph.node(node_id)
        found: set[str] = set()
        pending = list(self.predecessors[node_id])
        while pending:
            predecessor = pending.pop()
            if predecessor in found:
                continue
            found.add(predecessor)
            pending.extend(self.predecessors[predecessor])
        return tuple(candidate for candidate in self.order if candidate in found)


def compile_graph(graph: Graph) -> CompiledGraph:
    """Validate ``graph`` and derive predecessors and ``(depth, id)`` order.

    As in Microcosm, cycles are found by a depth-first depth calculation and
    predecessor tuples are sorted independently of declaration order.
    """

    if not isinstance(graph, Graph):
        raise TypeError("compile_graph expects a Graph.")
    by_id = {node.id: node for node in graph.nodes}
    source_names = {source.name for source in graph.sources}
    known = source_names.union(by_id)
    predecessors: dict[str, tuple[str, ...]] = {}
    for node in graph.nodes:
        unknown = [input_id for input_id in node.inputs if input_id not in known]
        if unknown:
            raise GraphError(
                f"Node {node.id!r} reads unknown input"
                f"{'s' if len(unknown) != 1 else ''} "
                + ", ".join(repr(value) for value in unknown)
                + "."
            )
        predecessors[node.id] = tuple(
            sorted(input_id for input_id in node.inputs if input_id in by_id)
        )

    depths: dict[str, int] = {}

    def depth_of(node_id: str, trail: tuple[str, ...]) -> int:
        if node_id in depths:
            return depths[node_id]
        if node_id in trail:
            start = trail.index(node_id)
            cycle = " -> ".join((*trail[start:], node_id))
            raise GraphError(f"Cycle: {cycle}.")
        parents = predecessors[node_id]
        depth = (
            0
            if not parents
            else 1 + max(depth_of(parent, (*trail, node_id)) for parent in parents)
        )
        depths[node_id] = depth
        return depth

    for node_id in by_id:
        depth_of(node_id, ())
    order = tuple(sorted(by_id, key=lambda node_id: (depths[node_id], node_id)))
    compiled = CompiledGraph(
        graph=graph,
        order=order,
        predecessors=predecessors,
        depths=depths,
    )
    for node in graph.nodes:
        if node.role != "release":
            continue
        gates = [
            ancestor
            for ancestor in compiled.ancestors(node.id)
            if by_id[ancestor].role == "gate"
        ]
        if not gates:
            raise GraphError(
                f"Release node {node.id!r} must have at least one gate ancestor."
            )
    return compiled
