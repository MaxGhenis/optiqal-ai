"""Exceptions shared by the Optiqal graph interface and runtime."""

from __future__ import annotations

__all__ = [
    "GraphError",
    "GraphRuntimeError",
    "KernelRegistrationError",
    "ManifestError",
    "NodeRejectedError",
    "NodeExecutionError",
    "StoreCorruptError",
    "StoreMissError",
    "StoreUnavailableError",
]


class GraphError(ValueError):
    """A graph declaration violates a compile-time invariant."""


class GraphRuntimeError(RuntimeError):
    """Base class for failures while executing or loading a graph."""


class KernelRegistrationError(GraphRuntimeError):
    """A kernel does not satisfy the frozen registry contract."""


class NodeRejectedError(GraphRuntimeError):
    """A non-gate node failed or a kernel returned an invalid result."""


# The specification calls this an execution error while the borrowed
# Microcosm runtime exposes NodeRejectedError. Both spellings name one contract.
NodeExecutionError = NodeRejectedError


class StoreMissError(GraphRuntimeError):
    """A requested content-addressed object is not present."""


class StoreCorruptError(GraphRuntimeError):
    """A stored object is present but fails validation."""


class StoreUnavailableError(GraphRuntimeError):
    """A stored format or dependency needed to restore it is unavailable."""


class ManifestError(GraphRuntimeError):
    """A manifest is malformed, altered, obsolete, or not certified."""
