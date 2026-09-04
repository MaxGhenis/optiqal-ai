"""Content identities and deterministic seeds for Optiqal graphs."""

from __future__ import annotations

import hashlib
import platform
import sys
from collections.abc import Mapping

from .canonical import canonical_json, normative, sha256_domain
from .decl import Node
from .kernel import Capabilities, Kernel, Numeric

__all__ = [
    "artifact_key",
    "node_key",
    "platform_fingerprint",
    "seed",
    "source_key",
]


def _hash_parts(domain: str, *parts: object) -> str:
    return sha256_domain(domain, canonical_json(parts))


def _capabilities_projection(capabilities: Capabilities) -> dict[str, object]:
    tolerance = capabilities.tolerance
    return {
        "dependencies": capabilities.dependencies,
        "determinism": capabilities.determinism.value,
        "numeric": capabilities.numeric.value,
        "role": capabilities.role,
        "tolerance": (
            None
            if tolerance is None
            else {"atol": tolerance.atol, "rtol": tolerance.rtol}
        ),
    }


def source_key(name: str, content: object) -> str:
    """Hash one named source's loaded normative content."""

    if not isinstance(name, str) or not name:
        raise ValueError("source name must be a non-empty string")
    return _hash_parts("source", name, normative(content))


def node_key(node: Node, input_keys: Mapping[str, str], kernel: Kernel) -> str:
    """Hash one node declaration, its declared inputs, and kernel identity."""

    if not isinstance(node, Node):
        raise TypeError("node_key expects a Node")
    if not isinstance(input_keys, Mapping):
        raise TypeError("input_keys must be a mapping")
    ordered_inputs: list[tuple[str, str]] = []
    for input_id in node.inputs:
        try:
            identity = input_keys[input_id]
        except KeyError as error:
            raise KeyError(
                f"Node {node.id!r} has no key for declared input {input_id!r}."
            ) from error
        if not isinstance(identity, str) or not identity:
            raise TypeError(f"Input key for {input_id!r} must be a non-empty string.")
        ordered_inputs.append((input_id, identity))
    implementation = kernel.implementation_hash()
    if not isinstance(implementation, str) or not implementation:
        raise TypeError(
            f"Kernel {kernel.ref!r} returned an invalid implementation hash."
        )
    capabilities = kernel.capabilities
    if not isinstance(capabilities, Capabilities):
        raise TypeError(f"Kernel {kernel.ref!r} has invalid capabilities.")
    fingerprint = (
        platform_fingerprint()
        if capabilities.numeric is Numeric.PLATFORM_BITWISE
        else None
    )
    return _hash_parts(
        "node",
        normative(node),
        tuple(ordered_inputs),
        implementation,
        _capabilities_projection(capabilities),
        fingerprint,
    )


def artifact_key(node_key: str) -> str:
    """Derive the value artifact identity from its producing node key."""

    if not isinstance(node_key, str) or not node_key:
        raise ValueError("node key must be a non-empty string")
    return _hash_parts("artifact", node_key)


def seed(node_key: str) -> int:
    """Derive the node's unsigned 64-bit little-endian RNG seed."""

    if not isinstance(node_key, str) or not node_key:
        raise ValueError("node key must be a non-empty string")
    digest = hashlib.sha256(b"seed\0" + node_key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little")


def platform_fingerprint() -> str:
    """Return architecture, OS, and Python minor without machine-local facts."""

    version = sys.version_info
    return f"{platform.machine()}/{sys.platform}/py{version.major}.{version.minor}"
