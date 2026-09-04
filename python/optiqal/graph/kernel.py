"""The frozen Optiqal kernel protocol.

A kernel is a pure function over the inputs, parameters, generator, and
numeric scopes in :class:`KernelContext`. Following Microcosm where the
Optiqal specification is silent, source identity hashes defining module bytes
and sorted installed dependency versions, while registering the same object
twice is idempotent.

This file is a frozen interface. Its hash is recorded in
``docs/rebuild/graph-interface.lock``.
"""

from __future__ import annotations

import hashlib
import inspect
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from importlib import metadata as importlib_metadata
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Protocol, runtime_checkable

import numpy as np

from .decl import ROLES, Node, Param
from .errors import KernelRegistrationError

__all__ = [
    "Capabilities",
    "Determinism",
    "Kernel",
    "KernelBase",
    "KernelContext",
    "KernelRegistry",
    "KernelResult",
    "Numeric",
    "NumericScope",
    "Tolerance",
    "source_hash",
]


class Determinism(StrEnum):
    """Whether output is fixed directly or by the executor-provided seed."""

    DETERMINISTIC = "deterministic"
    SEEDED = "seeded"


class Numeric(StrEnum):
    """The strength of a kernel's numeric reproducibility promise."""

    BITWISE = "bitwise"
    PLATFORM_BITWISE = "platform_bitwise"
    TOLERANCE_BOUND = "tolerance_bound"


@dataclass(frozen=True)
class Tolerance:
    """Relative and absolute bounds for tolerance-bound numeric output."""

    rtol: float = 0.0
    atol: float = 0.0

    def __post_init__(self) -> None:
        for name in ("rtol", "atol"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"Tolerance.{name} must be a number.")
            normalized = float(value)
            if not math.isfinite(normalized) or normalized < 0:
                raise ValueError(f"Tolerance.{name} must be finite and non-negative.")
            object.__setattr__(self, name, normalized)
        if self.rtol == 0.0 and self.atol == 0.0:
            raise ValueError("Tolerance must declare a positive rtol or atol.")


@dataclass(frozen=True)
class Capabilities:
    """A kernel's deterministic, numeric, role, and dependency contract."""

    determinism: Determinism
    numeric: Numeric = Numeric.BITWISE
    role: str = "compute"
    dependencies: tuple[str, ...] = ()
    tolerance: Tolerance | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.determinism, Determinism):
            raise TypeError("Capabilities.determinism must be a Determinism value.")
        if not isinstance(self.numeric, Numeric):
            raise TypeError("Capabilities.numeric must be a Numeric value.")
        if self.role not in ROLES:
            raise ValueError(f"Capabilities.role must be one of {ROLES}.")
        if not isinstance(self.dependencies, tuple) or any(
            not isinstance(item, str) or not item for item in self.dependencies
        ):
            raise TypeError(
                "Capabilities.dependencies must be a tuple of non-empty strings."
            )
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError(
                "Capabilities.dependencies must not repeat a distribution."
            )
        if self.numeric is Numeric.TOLERANCE_BOUND:
            if not isinstance(self.tolerance, Tolerance):
                raise ValueError(
                    "A tolerance_bound kernel requires a Tolerance declaration."
                )
        elif self.tolerance is not None:
            raise ValueError(
                "Only a tolerance_bound kernel may carry a Tolerance declaration."
            )


@dataclass(frozen=True)
class NumericScope:
    """The loosest numeric promise inherited by one kernel input.

    The interface names this type but does not prescribe its fields. This is
    Microcosm amendment 17's representation: class, optional bound, and the
    contributing platform fingerprint.
    """

    numeric: Numeric = Numeric.BITWISE
    tolerance: Tolerance | None = None
    platform: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.numeric, Numeric):
            raise TypeError("NumericScope.numeric must be a Numeric value.")
        if self.platform is not None and (
            not isinstance(self.platform, str) or not self.platform
        ):
            raise TypeError("NumericScope.platform must be a non-empty string or None.")
        if self.numeric is Numeric.TOLERANCE_BOUND:
            if not isinstance(self.tolerance, Tolerance):
                raise ValueError("A tolerance_bound scope requires a Tolerance.")
        elif self.tolerance is not None:
            raise ValueError("Only a tolerance_bound scope may carry a Tolerance.")
        if self.numeric is Numeric.BITWISE and self.platform is not None:
            raise ValueError("A bitwise scope cannot be platform-specific.")
        if self.numeric is Numeric.PLATFORM_BITWISE and self.platform is None:
            raise ValueError(
                "A platform_bitwise scope requires a platform fingerprint."
            )


@dataclass(frozen=True)
class KernelContext:
    """Everything a kernel may observe during one invocation."""

    node: Node
    inputs: Mapping[str, object]
    params: Mapping[str, Param]
    rng: np.random.Generator
    numerics: Mapping[str, NumericScope]

    def __post_init__(self) -> None:
        if not isinstance(self.node, Node):
            raise TypeError("KernelContext.node must be a Node.")
        if not isinstance(self.inputs, Mapping):
            raise TypeError("KernelContext.inputs must be a mapping.")
        if not isinstance(self.params, Mapping):
            raise TypeError("KernelContext.params must be a mapping.")
        if not isinstance(self.rng, np.random.Generator):
            raise TypeError("KernelContext.rng must be a numpy Generator.")
        if not isinstance(self.numerics, Mapping) or any(
            not isinstance(scope, NumericScope) for scope in self.numerics.values()
        ):
            raise TypeError("KernelContext.numerics must map inputs to NumericScope.")
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(self, "numerics", MappingProxyType(dict(self.numerics)))


@dataclass(frozen=True)
class KernelResult:
    """A canonical value, deterministic receipt facts, and opaque artifacts."""

    value: object
    receipt: Mapping[str, object] = field(default_factory=dict)
    artifacts: Mapping[str, bytes] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, Mapping):
            raise TypeError("KernelResult.receipt must be a mapping.")
        if not isinstance(self.artifacts, Mapping):
            raise TypeError("KernelResult.artifacts must be a mapping.")
        receipt: dict[str, object] = {}
        for name, value in self.receipt.items():
            if not isinstance(name, str):
                raise TypeError("KernelResult.receipt keys must be strings.")
            receipt[name] = value
        artifacts: dict[str, bytes] = {}
        for name, payload in self.artifacts.items():
            if not isinstance(name, str) or not name:
                raise TypeError(
                    "KernelResult artifact names must be non-empty strings."
                )
            if not isinstance(payload, bytes):
                raise TypeError(f"KernelResult artifact {name!r} must be bytes.")
            artifacts[name] = payload
        object.__setattr__(self, "receipt", MappingProxyType(receipt))
        object.__setattr__(self, "artifacts", MappingProxyType(artifacts))


@runtime_checkable
class Kernel(Protocol):
    """A registered pure computation named by a versioned reference."""

    ref: str
    capabilities: Capabilities

    def implementation_hash(self) -> str:
        """Return the source-and-dependency implementation identity."""

        ...

    def run(self, context: KernelContext) -> KernelResult:
        """Compute one value without mutating ``context``."""

        ...


def source_hash(
    *objects: ModuleType | type | Callable[..., object],
    dependencies: tuple[str, ...] = (),
) -> str:
    """Hash defining module bytes and declared installed dependency versions.

    As in Microcosm, paths and interpreter bytes are excluded. Each defining
    module is included once, in caller order, and dependency names are sorted.
    """

    digest = hashlib.sha256(b"optiqal-graph/source-hash/1\n")
    seen: set[str] = set()
    for obj in objects:
        module = obj if isinstance(obj, ModuleType) else inspect.getmodule(obj)
        if module is None or module.__file__ is None:
            raise ValueError(f"Cannot locate source for {obj!r}.")
        path = Path(module.__file__).resolve()
        module_name = module.__name__
        resolved_path = str(path)
        if resolved_path in seen:
            continue
        seen.add(resolved_path)
        if not path.is_file():
            raise ValueError(
                f"{obj!r} has no source file on disk; interactive kernels cannot "
                "carry an implementation hash."
            )
        content = path.read_bytes()
        digest.update(module_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "little"))
        digest.update(content)
    for distribution in sorted(dependencies):
        if not isinstance(distribution, str) or not distribution:
            raise TypeError("source_hash dependencies must be non-empty strings.")
        try:
            version = importlib_metadata.version(distribution)
        except importlib_metadata.PackageNotFoundError as error:
            raise ValueError(
                f"Dependency {distribution!r} is declared but not installed."
            ) from error
        digest.update(f"{distribution}=={version}\n".encode("utf-8"))
    return digest.hexdigest()


class KernelBase:
    """Default implementation identity for kernels defined in one module."""

    ref: str
    capabilities: Capabilities

    def implementation_hash(self) -> str:
        return source_hash(type(self), dependencies=self.capabilities.dependencies)


class KernelRegistry:
    """A validated mapping from versioned kernel references to kernels."""

    def __init__(self) -> None:
        self._kernels: dict[str, Kernel] = {}

    def register(self, kernel: Kernel) -> Kernel:
        """Register ``kernel``; re-registering the same object is idempotent."""

        if not isinstance(kernel, Kernel):
            raise KernelRegistrationError(
                f"{kernel!r} does not satisfy the Kernel protocol."
            )
        if not isinstance(kernel.ref, str) or not kernel.ref:
            raise KernelRegistrationError("Kernel.ref must be a non-empty string.")
        if not isinstance(kernel.capabilities, Capabilities):
            raise KernelRegistrationError(
                f"Kernel {kernel.ref!r} has invalid capabilities."
            )
        incumbent = self._kernels.get(kernel.ref)
        if incumbent is not None and incumbent is not kernel:
            raise KernelRegistrationError(
                f"Kernel {kernel.ref!r} is already registered."
            )
        self._kernels[kernel.ref] = kernel
        return kernel

    def get(self, ref: str) -> Kernel:
        """Resolve one reference."""

        try:
            return self._kernels[ref]
        except KeyError as error:
            raise KeyError(f"No kernel registered as {ref!r}.") from error

    def refs(self) -> tuple[str, ...]:
        """Return registered references in canonical order."""

        return tuple(sorted(self._kernels))

    def implementation_hash(self, ref: str) -> str:
        """Return the registered implementation identity for ``ref``."""

        return self.get(ref).implementation_hash()

    def as_mapping(self) -> Mapping[str, Kernel]:
        """Return a detached read-only registry view."""

        return MappingProxyType(dict(self._kernels))
